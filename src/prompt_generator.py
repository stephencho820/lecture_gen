# src/prompt_generator.py
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
import openai
from openai.error import OpenAIError

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

DEFAULT_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

STYLE_RULES = """
공통 스타일 규칙(반드시 지켜):
- 16:9, realistic, moody lighting
- 사람은 반드시 실루엣(얼굴 디테일/눈/표정 노출 금지). 손/몸 실루엣 정도는 가능.
- 하지만 유명인물(머스크, 버핏 등) 모습은 예외로 가능.
- 글자/숫자/워터마크/간판/차트 UI/앱 UI/신문 헤드라인 등 “읽을 수 있는 요소” 전부 금지.
- 직접적인 기업 로고(Apple, Google, Tesla 등) 은 가능. 
- 금융 지표는 “추상적 상징물”로만 (빛나는 그래프 형태조차 텍스트처럼 보일 수 있으니 피함)
- 배경은 글로벌/도시/실내 등을 장면에 맞게. 한국 시청자 정서(서울/야경/집/사무실 분위기) 은 “느낌”으로만.
- 너무 과하지 않은 그림으로 현실감 있게. 지나치게 환상적/초현실적/만화적 금지.
"""

OUTPUT_FORMAT = """
반환은 JSON 하나로만 해. (코드블록 금지)
형식:
{
  "keywords": ["...","..."],
  "mood": "짧은 한국어 단어/구",
  "metaphor": "한 문장(한국어)",
  "image_prompt": "영문 프롬프트 1개 (한 문단). 반드시 16:9, no text 등을 포함."
}
"""

def _call_prompt_llm(scene_script: str, *, scene_id: int) -> Dict[str, Any]:
    system = "You are a senior creative director specialized in cinematic symbolic visuals for finance/education videos."
    user = f"""
아래 나레이션 구간을 보고, '상징적 장면' 1개를 설계해줘.

[Scene {scene_id} 나레이션]
{scene_script}

{STYLE_RULES}

추가 힌트:
- 경제/투자 불안: '손끝이 멈춤', '높은 환율', '계좌 흔들림', '시퀀스 리스크', '장기투자/습관', '인플레이션', '성공' 같은 정서를 상징으로 표현.
- 너무 직접적인 숫자/지수 이름(S&P500 등)은 이미지에 쓰지 말고, 분위기와 비유로만.
- image_prompt는 영어로, “no text, no numbers, no logos, no watermark”를 명시해.

{OUTPUT_FORMAT}
""".strip()

    try:
        resp = openai.ChatCompletion.create(
            model=DEFAULT_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
        )
    except OpenAIError as e:
        raise RuntimeError(f"OpenAI API error: {e}")

    content = resp.choices[0].message["content"].strip()
    data = json.loads(content)  # JSON only 강제

    # 최소 방어
    for k in ["keywords", "mood", "metaphor", "image_prompt"]:
        if k not in data:
            raise ValueError(f"모델 응답에 '{k}'가 없습니다: {data}")

    # image_prompt에 필수 안전장치 삽입
    ip = str(data["image_prompt"]).strip()
    must = ["16:9", "realistic", "cinematic", "no text", "no numbers", "no logos", "no watermark"]
    for m in must:
        if m.lower() not in ip.lower():
            ip += f", {m}"
    data["image_prompt"] = ip

    return data


def fill_scene_prompts(
    scene_plan_path: Path,
    *,
    overwrite: bool = False,
    sleep_sec: float = 0.3,
) -> Path:
    payload = json.loads(scene_plan_path.read_text(encoding="utf-8"))
    scenes: List[Dict[str, Any]] = payload.get("scenes", [])
    if not scenes:
        raise ValueError("scene_plan.json에 scenes가 없습니다.")

    updated = 0
    for s in scenes:
        need = overwrite or (s.get("image_prompt") is None)
        if not need:
            continue

        scene_id = int(s["id"])
        script = str(s.get("script", "")).strip()
        if not script:
            continue

        print(f"[PROMPT] scene {scene_id}: generating...")
        data = _call_prompt_llm(script, scene_id=scene_id)

        s["keywords"] = data["keywords"]
        s["mood"] = data["mood"]
        s["metaphor"] = data["metaphor"]
        s["image_prompt"] = data["image_prompt"]
        updated += 1

        time.sleep(sleep_sec)

    payload["scenes"] = scenes
    payload["prompts_filled"] = True
    payload["prompts_updated_count"] = updated

    out_path = scene_plan_path.parent / scene_plan_path.name.replace(".json", "_filled.json")
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] filled scene plan saved: {out_path} (updated={updated})")
    return out_path
