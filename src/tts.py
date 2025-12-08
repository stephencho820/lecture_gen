import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from typecast.client import Typecast
from typecast.models import TTSRequest, Prompt, Output, LanguageCode
from typecast.exceptions import TypecastError

load_dotenv()

# 환경 변수에서 API 키/보이스 ID 가져오기
TYPECAST_API_KEY = os.getenv("TYPECAST_API_KEY")
TYPECAST_VOICE_ID = os.getenv("TYPECAST_VOICE_ID")

if not TYPECAST_API_KEY:
    raise RuntimeError("TYPECAST_API_KEY 가 설정되어 있지 않습니다. .env 또는 환경변수에 추가해 주세요.")

if not TYPECAST_VOICE_ID:
    raise RuntimeError("TYPECAST_VOICE_ID 가 설정되어 있지 않습니다. 사용하려는 Typecast 목소리의 voice_id를 넣어 주세요.")

# Typecast 클라이언트 초기화
cli = Typecast(api_key=TYPECAST_API_KEY)

# Typecast API 스펙상 text 최대 5000자 → 여유 두고 4000자로 쪼갬 :contentReference[oaicite:3]{index=3}
MAX_CHARS_PER_CHUNK = 1800


def _chunk_text(text: str, max_len: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """
    Typecast TTS text 길이 제한(최대 5000자)을 고려해서
    텍스트를 여러 chunk로 나누는 함수.
    - 문단 → 문장 → 하드컷 순으로 잘게 나눔.
    """
    text = text.strip()
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    buf: list[str] = []

    paragraphs = text.split("\n\n")
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        if len(paragraph) > max_len:
            # 문단이 너무 길면 문장 단위로 다시 쪼개기
            sentences: list[str] = []
            tmp = ""
            for ch in paragraph:
                tmp += ch
                if ch in ".?!。？！":
                    sentences.append(tmp.strip())
                    tmp = ""
            if tmp.strip():
                sentences.append(tmp.strip())

            for s in sentences:
                if not s:
                    continue
                if len(s) > max_len:
                    # 문장 자체가 너무 길면 하드컷
                    for i in range(0, len(s), max_len):
                        chunks.append(s[i : i + max_len])
                    continue

                joined = (" ".join(buf) + " " + s).strip()
                if len(joined) > max_len:
                    chunks.append(" ".join(buf))
                    buf = [s]
                else:
                    buf.append(s)
        else:
            joined = ("\n\n".join(buf + [paragraph])).strip()
            if len(joined) > max_len:
                chunks.append("\n\n".join(buf))
                buf = [paragraph]
            else:
                buf.append(paragraph)

    if buf:
        chunks.append("\n\n".join(buf))

    # 마지막 방어: 혹시 여전히 너무 긴 chunk 있으면 하드컷
    final_chunks: list[str] = []
    for c in chunks:
        c = c.strip()
        if not c:
            continue
        if len(c) <= max_len:
            final_chunks.append(c)
        else:
            for i in range(0, len(c), max_len):
                final_chunks.append(c[i : i + max_len])

    return final_chunks


def script_to_speech(
    script_text: str,
    output_base_path: Path,
    *,
    # 톤/스타일 기본값 (나중에 main.py에서 바꾸고 싶으면 여기 인자만 조절)
    emotion_preset: str = "normal",   # normal / happy / sad / angry :contentReference[oaicite:4]{index=4}
    emotion_intensity: float = 0.8,   # 0.0 ~ 2.0
    volume: int = 110,                # 0 ~ 200
    audio_pitch: int = -1,            # -12 ~ +12 (조금 낮게, 진중한 느낌)
    audio_tempo: float = 1.0,         # 0.5 ~ 2.0
    audio_format: str = "mp3",        # "wav" 또는 "mp3"
) -> List[Path]:
    """
    Typecast TTS로 스크립트를 여러 파트로 나누어 음성을 생성.
    길면 base_stem_part1.mp3, part2.mp3 ... 형식으로 저장.

    반환: 생성된 오디오 파일 경로 리스트
    """
    output_base_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = _chunk_text(script_text, max_len=MAX_CHARS_PER_CHUNK)
    print(f"[INFO] Typecast TTS용 텍스트를 {len(chunks)}개 파트로 분할했습니다.")
    for i, c in enumerate(chunks, start=1):
        print(f"  - chunk {i}: {len(c)} chars")

    result_paths: list[Path] = []

    stem = output_base_path.stem
    parent = output_base_path.parent

    for idx, chunk in enumerate(chunks, start=1):
        if len(chunks) == 1:
            out_path = parent / f"{stem}.{audio_format}"
        else:
            out_path = parent / f"{stem}__part{idx}.{audio_format}"

        print(f"[INFO] Typecast TTS 생성 중... ({idx}/{len(chunks)}) -> {out_path}")

        req = TTSRequest(
            text=chunk,
            model="ssfm-v21",
            voice_id=TYPECAST_VOICE_ID,
            language=LanguageCode.KOR,   # 한국어 고정 :contentReference[oaicite:5]{index=5}
            prompt=Prompt(
                emotion_preset=emotion_preset,
                emotion_intensity=emotion_intensity,
            ),
            output=Output(
                volume=volume,
                audio_pitch=audio_pitch,
                audio_tempo=audio_tempo,
                audio_format=audio_format,
            ),
            # seed=42  # 항상 동일한 결과를 원하면 seed 고정도 가능
        )

        try:
            response = cli.text_to_speech(req)
        except TypecastError as e:
            print(f"[ERROR] Typecast TTS Error: {e.message} (status={e.status_code})")
            raise

        # SDK는 audio_data 바이트를 반환함 :contentReference[oaicite:6]{index=6}
        with open(out_path, "wb") as f:
            f.write(response.audio_data)

        result_paths.append(out_path)

    print("[INFO] Typecast TTS 생성 완료.")
    return result_paths
