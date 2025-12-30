import os

from dotenv import load_dotenv
import openai
from openai.error import OpenAIError

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


def rewrite_for_rich_mindset_channel(original_script: str) -> str:
    """
    전사된 원본 스크립트를 기반으로:
    - 분량: 원본의 0.9배 ~ 1.1배 유지
    - 핵심 지식/논리: 유지 또는 보강
    - 예시/스토리: 전부 새로 구성
    - 톤: 기존과 비슷한 톤으로 구성 (이건 강의가 아님. 생각을 전달하는 유투브 채널임)
    - 반드시 지켜야하는 룰: 스크립트를 tts로 변환하기 때문에 '1.'과 같은 bullet을 사용하면 안되고 '첫째'라고 표현해야함.
    - '강의', '오늘'이라는 표현 금지
    """
    original_len = len(original_script)

    system_prompt = """
당신은 '부자의 사고법' 유튜브 채널을 위한 전문 스토리텔러입니다.
...
""".strip()

    user_prompt = f"""
다음 텍스트는 하나의 스토리를 전사한 원본 스크립트입니다.
...
[원본 스크립트]
--------------------
{original_script}
--------------------
""".strip()

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=8000,
        )
    except OpenAIError as e:
        raise RuntimeError(f"OpenAI API error: {e}")

    return response.choices[0].message["content"]
