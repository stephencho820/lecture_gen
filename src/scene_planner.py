# src/scene_planner.py
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Scene:
    id: int
    start: float
    end: float
    duration: float
    script: str

    # 다음 단계(GPT)에서 채울 필드들
    keywords: List[str] | None = None
    mood: str | None = None
    metaphor: str | None = None
    image_prompt: str | None = None


def _clean_text(s: str) -> str:
    s = s.replace("\n", " ").strip()
    # 중복 공백 정리
    while "  " in s:
        s = s.replace("  ", " ")
    return s


def build_scenes_from_segments(
    segments: List[Dict[str, Any]],
    *,
    target_sec: float = 13.0,        # 평균 목표 길이
    min_sec: float = 8.0,            # 너무 짧은 컷 방지
    max_sec: float = 18.0,           # 너무 긴 컷 방지(프롬프트 품질도 떨어짐)
    max_chars: int = 240,            # 한 scene 텍스트가 너무 길면 자막/프롬프트가 난잡해짐
) -> List[Scene]:
    """
    segments를 시간 기반으로 묶어 scene 리스트를 만든다.
    - target_sec 근처에서 자르되,
    - 문장 마침표(.,?!, …)가 있으면 거기에서 끊는 것을 우선한다.
    - max_sec를 넘기면 강제로 컷.
    - 텍스트가 너무 길어도 끊는다.
    """
    scenes: List[Scene] = []
    buf_text: List[str] = []
    buf_start: Optional[float] = None
    buf_end: Optional[float] = None

    def flush():
        nonlocal buf_text, buf_start, buf_end
        if buf_start is None or buf_end is None:
            buf_text, buf_start, buf_end = [], None, None
            return
        script = _clean_text(" ".join(buf_text))
        if script:
            scene_id = len(scenes) + 1
            scenes.append(
                Scene(
                    id=scene_id,
                    start=buf_start,
                    end=buf_end,
                    duration=round(buf_end - buf_start, 3),
                    script=script,
                )
            )
        buf_text, buf_start, buf_end = [], None, None

    def is_good_break(text: str) -> bool:
        # 문장 경계로 보이는 조건들
        return text.endswith((".", "!", "?", "…", "。", "！", "？"))

    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        text = str(seg.get("text", "")).strip()
        if not text:
            continue

        if buf_start is None:
            buf_start = start
        buf_end = end
        buf_text.append(text)

        current_dur = (buf_end - buf_start) if (buf_start is not None and buf_end is not None) else 0.0
        current_script = _clean_text(" ".join(buf_text))

        # 1) 너무 길면 강제 컷
        if current_dur >= max_sec or len(current_script) >= max_chars:
            flush()
            continue

        # 2) 목표 길이 이상이면 “자연스러운 끊김”이면 컷
        if current_dur >= target_sec:
            if current_dur >= min_sec and is_good_break(text):
                flush()
                continue

            # 목표는 넘었는데 마침표가 없으면, 조금 더 기다리되 max_sec 이전에 적당히 컷
            # -> 다음 segments에서 마침표가 나오면 거기서 flush 되거나,
            # -> max_sec/ max_chars에서 flush 됨
            pass

    # 남은 버퍼
    flush()

    # (후처리) 마지막 scene이 너무 짧으면 앞 scene에 합치기
    if len(scenes) >= 2 and scenes[-1].duration < min_sec:
        last = scenes.pop()
        prev = scenes[-1]
        prev.end = last.end
        prev.duration = round(prev.end - prev.start, 3)
        prev.script = _clean_text(prev.script + " " + last.script)

    return scenes


def load_timestamped_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "segments" not in data:
        raise ValueError("timestamped.json에 'segments'가 없습니다.")
    return data


def save_scene_plan(
    scenes: List[Scene],
    out_path: Path,
    *,
    source_timestamped: str,
) -> Path:
    payload = {
        "source_timestamped": source_timestamped,
        "scene_count": len(scenes),
        "scenes": [asdict(s) for s in scenes],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path