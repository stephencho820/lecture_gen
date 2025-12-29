# src/transcriber_timestamped.py
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError
from pydub import AudioSegment

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ timestamp 필요할 땐 whisper-1 사용 (verbose_json + segments 지원)
DEFAULT_TS_MODEL = "whisper-1"


@dataclass
class Segment:
    start: float
    end: float
    text: str


def get_audio_duration_seconds(audio_path: Path) -> float:
    audio = AudioSegment.from_file(audio_path)
    return len(audio) / 1000.0


def transcribe_single_file_timestamped(
    audio_path: Path,
    *,
    language: str = "ko",
    model: str = DEFAULT_TS_MODEL,
    max_retries: int = 3,
    retry_delay: float = 3.0,
) -> Dict[str, Any]:
    """
    단일 파일을 timestamp 포함으로 전사.
    whisper-1: verbose_json + timestamp_granularities 로 segments 확보 가능.
    """
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[INFO] timestamp 전사 시도 {attempt}/{max_retries} ... ({audio_path})")
            with open(audio_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model=model,
                    file=f,
                    language=language,
                    response_format="verbose_json",
                    # ✅ segments 타임스탬프 활성화
                    timestamp_granularities=["segment"],
                )

            # SDK가 dict/객체 어느 형태로 올지 방어
            data = result if isinstance(result, dict) else getattr(result, "model_dump", lambda: {})()
            if not data:
                data = {
                    "text": getattr(result, "text", ""),
                    "segments": getattr(result, "segments", None),
                }

            segments_raw = data.get("segments")
            if not segments_raw:
                raise RuntimeError(
                    "verbose_json 응답에서 segments를 찾지 못했습니다. "
                    "timestamp_granularities 설정 또는 모델을 확인하세요."
                )

            segments: List[Segment] = []
            for s in segments_raw:
                start = s["start"] if isinstance(s, dict) else getattr(s, "start")
                end = s["end"] if isinstance(s, dict) else getattr(s, "end")
                text = s["text"] if isinstance(s, dict) else getattr(s, "text")
                segments.append(Segment(float(start), float(end), str(text).strip()))

            full_text = data.get("text") or "\n".join(seg.text for seg in segments)

            print("[INFO] timestamp 전사 성공")
            return {
                "text": full_text,
                "segments": [seg.__dict__ for seg in segments],
            }

        except OpenAIError as e:
            last_error = e
            print(f"[WARN] timestamp 전사 오류 (시도 {attempt}): {e}")
            if hasattr(e, "status") and getattr(e, "status", 500) < 500:
                print("[ERROR] 클라이언트 오류(4xx)로 재시도하지 않습니다.")
                break
            if attempt < max_retries:
                print(f"[INFO] {retry_delay}초 후 재시도...")
                time.sleep(retry_delay)

        except Exception as e:
            last_error = e
            print(f"[ERROR] 알 수 없는 오류: {e}")
            break

    raise RuntimeError(f"timestamp 전사 실패. 마지막 오류: {last_error}") from last_error


def merge_timestamped_parts(part_results: List[Dict[str, Any]], part_paths: List[Path]) -> Dict[str, Any]:
    if len(part_results) != len(part_paths):
        raise ValueError("part_results와 part_paths 길이가 일치해야 합니다.")

    merged_segments: List[Dict[str, Any]] = []
    merged_text_parts: List[str] = []

    offset = 0.0
    for idx, (res, path) in enumerate(zip(part_results, part_paths), start=1):
        segs = res.get("segments", [])
        print(f"[INFO] 병합: part{idx} segments={len(segs)} offset={offset:.2f}s")

        for s in segs:
            merged_segments.append(
                {
                    "start": float(s["start"]) + offset,
                    "end": float(s["end"]) + offset,
                    "text": str(s["text"]).strip(),
                }
            )

        merged_text_parts.append(res.get("text", "").strip())
        offset += get_audio_duration_seconds(path)

    merged_text = "\n\n".join([t for t in merged_text_parts if t])
    return {"text": merged_text, "segments": merged_segments}


def transcribe_parts_timestamped(
    audio_parts: List[Path],
    *,
    language: str = "ko",
    model: str = DEFAULT_TS_MODEL,
) -> Dict[str, Any]:
    for p in audio_parts:
        if not p.exists():
            raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {p}")

    part_results: List[Dict[str, Any]] = []
    for idx, p in enumerate(audio_parts, start=1):
        print(f"[INFO] [{idx}/{len(audio_parts)}] timestamp 전사 시작: {p}")
        part_results.append(
            transcribe_single_file_timestamped(p, language=language, model=model)
        )

    return merge_timestamped_parts(part_results, audio_parts)