import os
import time
from pathlib import Path
from typing import List

from dotenv import load_dotenv
import openai
from openai.error import OpenAIError
from pydub import AudioSegment

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


def split_audio(
    audio_path: Path,
    chunk_minutes: int = 10,
) -> List[Path]:
    """
    긴 mp3 파일을 chunk_minutes 단위(분)로 잘라 임시 파일 리스트를 반환.
    """
    print(f"[INFO] 오디오 분할 중... ({chunk_minutes}분 단위)")

    audio = AudioSegment.from_file(audio_path)
    duration_ms = len(audio)
    chunk_ms = chunk_minutes * 60 * 1000

    chunks_dir = audio_path.parent / "_chunks"
    chunks_dir.mkdir(exist_ok=True)

    chunk_paths: List[Path] = []

    for i, start_ms in enumerate(range(0, duration_ms, chunk_ms)):
        end_ms = min(start_ms + chunk_ms, duration_ms)
        chunk_audio = audio[start_ms:end_ms]
        chunk_path = chunks_dir / f"{audio_path.stem}_part{i + 1}.mp3"
        chunk_audio.export(chunk_path, format="mp3")
        chunk_paths.append(chunk_path)
        print(f"[INFO] 분할 파일 생성: {chunk_path} ({start_ms/1000:.1f}s ~ {end_ms/1000:.1f}s)")

    return chunk_paths


def transcribe_single_file(
    audio_path: Path,
    language: str = "ko",
    max_retries: int = 3,
    retry_delay: float = 3.0,
) -> str:
    """
    단일 오디오 파일에 대해 STT 수행 (리트라이 포함).
    openai==0.28.1 기준.
    """
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[INFO] 전사 시도 {attempt}/{max_retries} ... ({audio_path})")
            with open(audio_path, "rb") as f:
                text = openai.Audio.transcribe(
                    model="whisper-1",
                    file=f,
                    language=language,
                    response_format="text",
                )

            print("[INFO] 전사 성공")
            return text.strip()

        except OpenAIError as e:
            last_error = e
            print(f"[WARN] 전사 중 오류 발생 (시도 {attempt}): {e}")
            if hasattr(e, "http_status") and getattr(e, "http_status", 500) < 500:
                print("[ERROR] 클라이언트 오류(4xx)로 재시도하지 않습니다.")
                break

            if attempt < max_retries:
                print(f"[INFO] {retry_delay}초 후 재시도합니다...")
                time.sleep(retry_delay)

        except Exception as e:
            last_error = e
            print(f"[ERROR] 알 수 없는 오류 발생: {e}")
            break

    raise RuntimeError(
        f"음성 전사에 실패했습니다. 마지막 오류: {last_error}"
    ) from last_error


def transcribe_audio(
    audio_path: Path,
    language: str = "ko",
    chunk_minutes: int = 10,
) -> str:
    """
    긴 오디오 파일을 chunk_minutes 분 단위로 잘라 순차적으로 전사하고,
    결과 텍스트를 이어 붙여 하나의 문자열로 반환.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

    print(f"[INFO] 전체 음성 전사 시작: {audio_path}")

    # 1) 오디오 분할
    chunk_paths = split_audio(audio_path, chunk_minutes=chunk_minutes)

    # 2) 각 chunk 전사
    all_text_parts: List[str] = []
    for idx, chunk_path in enumerate(chunk_paths, start=1):
        print(f"[INFO] [{idx}/{len(chunk_paths)}] chunk 전사 시작: {chunk_path}")
        text = transcribe_single_file(chunk_path, language=language)
        all_text_parts.append(text.strip())
        print(f"[INFO] [{idx}/{len(chunk_paths)}] chunk 전사 완료")

    # 3) 전체 텍스트 결합
    full_text = "\n\n".join(all_text_parts)
    print("[INFO] 전체 전사 완료")

    return full_text
