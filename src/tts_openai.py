import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 한 번에 TTS에 넣을 최대 글자 수 (보수적으로 줄여서 안전하게)
MAX_CHARS_PER_CHUNK = 1500  # 필요하면 더 줄여도 됨 (ex: 1200)


def _chunk_text(text: str, max_len: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """
    TTS 입력 길이 제한 때문에 텍스트를 잘라주는 함수.
    - 문단 -> 문장 순으로 최대한 자연스럽게 잘라서 여러 chunk로 나눔.
    """
    text = text.strip()
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    buf: list[str] = []

    # 1차: 문단 단위로 쪼개기
    paragraphs = text.split("\n\n")
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        # 문단이 너무 길면 문장 단위로 다시 쪼갬
        if len(paragraph) > max_len:
            # 한국어 기준으로 대충 문장 단위로 쪼개기
            # 온점/물음표/느낌표 기준
            sentences = []
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
                    # 여기까지 와도 너무 긴 문장이면 그냥 잘라버림
                    for i in range(0, len(s), max_len):
                        hard_chunk = s[i : i + max_len]
                        chunks.append(hard_chunk)
                    continue

                if len(" ".join(buf) + " " + s) > max_len:
                    chunks.append(" ".join(buf))
                    buf = [s]
                else:
                    buf.append(s)
        else:
            if len("\n\n".join(buf + [paragraph])) > max_len:
                chunks.append("\n\n".join(buf))
                buf = [paragraph]
            else:
                buf.append(paragraph)

    if buf:
        chunks.append("\n\n".join(buf))

    # 마지막 방어: 혹시라도 여전히 너무 긴 chunk가 있으면 하드컷
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
    model: str = "gpt-4o-mini-tts",
    voice: str = "onyx",
    instructions: str = "진중한 톤의 한국인 자연스러운 톤으로, 차분하지만 정말 인간이 읽는 것 처럼 때론 감정적으로 읽어 주세요.",
) -> List[Path]:
    """
    스크립트를 여러 파트로 나누어 TTS 수행.
    - 길면 sample_stem_part1.mp3, part2.mp3 ... 이런 식으로 저장.
    """
    output_base_path.parent.mkdir(parents=True, exist_ok=True)

    chunks = _chunk_text(script_text)
    print(f"[INFO] TTS용 텍스트를 {len(chunks)}개 파트로 분할했습니다.")
    for i, c in enumerate(chunks, start=1):
        print(f"  - chunk {i}: {len(c)} chars")

    result_paths: list[Path] = []

    stem = output_base_path.stem
    parent = output_base_path.parent

    for idx, chunk in enumerate(chunks, start=1):
        if len(chunks) == 1:
            out_path = parent / f"{stem}.mp3"
        else:
            out_path = parent / f"{stem}_part{idx}.mp3"

        print(f"[INFO] TTS 생성 중... ({idx}/{len(chunks)}) -> {out_path}")

        try:
            with client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=chunk,
                instructions=instructions,
                response_format="mp3",
            ) as response:
                response.stream_to_file(out_path)

        except OpenAIError as e:
            msg = str(e)
            print(f"[ERROR] TTS 호출 중 오류 발생: {msg}")
            if "shorten your input" in msg.lower():
                raise RuntimeError(
                    "TTS 입력이 너무 깁니다. MAX_CHARS_PER_CHUNK 값을 더 줄여서 다시 시도해 주세요."
                ) from e
            else:
                raise

        result_paths.append(out_path)

    print("[INFO] TTS 생성 완료.")
    return result_paths
