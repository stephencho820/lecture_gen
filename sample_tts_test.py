import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 테스트할 목소리 목록
VOICES = ["onyx", "ballad", "sage", "alloy", "verse", "coral", "echo"]

# 테스트 문장 (원하는 문장으로 변경 가능)
TEST_SENTENCE = "오늘은 부자의 사고방식이 어떻게 인생을 바꾸는지 간단히 설명드리겠습니다."

OUTPUT_DIR = Path("tts_samples")
OUTPUT_DIR.mkdir(exist_ok=True)


def create_tts_sample(voice: str, text: str):
    """하나의 목소리 샘플을 mp3로 생성"""
    output_path = OUTPUT_DIR / f"sample_{voice}.mp3"
    print(f"[INFO] Generating sample for voice: {voice}")

    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        instructions="낮고 차분하며 자연스러운 강의 톤으로 읽어 주세요.",
        response_format="mp3",
    ) as response:
        response.stream_to_file(output_path)

    print(f"[INFO] Saved → {output_path}")


def main():
    print("[INFO] TTS Sample Generation Started")

    for v in VOICES:
        create_tts_sample(v, TEST_SENTENCE)

    print("\n🎧 모든 샘플 생성 완료!")
    print("➡ tts_samples/ 폴더에서 목소리를 비교해보세요.")


if __name__ == "__main__":
    main()
