import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def transcribe_audio(audio_path: Path, language: str = "ko") -> str:
    """
    OpenAI Audio API(gpt-4o-mini-transcribe)를 사용해
    오디오 파일을 텍스트로 전사.

    :param audio_path: mp3 등 오디오 파일 경로
    :param language: ISO-639-1 언어 코드 (예: 'ko', 'en')
    :return: 전사된 텍스트
    """
    print("[INFO] 음성 전사 중...")

    with open(audio_path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",  # gpt-4o 계열 STT 모델
            file=f,
            language=language,
        )

    print("[INFO] 전사 완료")
    return transcription.text
