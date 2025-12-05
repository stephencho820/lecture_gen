import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def script_to_speech(
    script_text: str,
    output_path: Path,
    *,
    model: str = "gpt-4o-mini-tts",
    voice: str = "onyx",
    instructions: str = "낮은 톤의 진중한 한국인 남성 강의 톤으로, 차분하고 또박또박 읽어 주세요.",
) -> Path:
    """
    강의 스크립트를 TTS로 변환해서 mp3로 저장.

    - model: gpt-4o-mini-tts / tts-1 / tts-1-hd
      * instructions 옵션은 gpt-4o-mini-tts에서만 동작
    - voice: alloy, ash, ballad, coral, echo, fable, onyx, nova, sage, shimmer, verse
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 길이 제한 안내
    if len(script_text) > 4000:
        print(
            "[WARN] 스크립트 길이가 4096자를 초과할 수 있습니다. "
            "Error 발생 시 나중에 섹션 단위로 잘라서 호출하는 로직을 추가하는 걸 추천합니다."
        )

    print(f"[INFO] TTS 생성 중... (model={model}, voice={voice})")

    # 공식 문서 기준: with_streaming_response 사용 예시
    # https://platform.openai.com/docs/api-reference/audio/createSpeech
    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=script_text,
        instructions=instructions,
        response_format="mp3",
    ) as response:
        response.stream_to_file(output_path)

    print(f"[INFO] TTS 오디오 저장 완료: {output_path}")
    return output_path
