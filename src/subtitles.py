from typing import List, Dict
import re


def _fmt_srt_time(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _split_to_chunks(
    text: str,
    *,
    max_chars: int = 26,
    min_chars: int = 10,
    max_lines_per_segment: int = 3,
) -> List[str]:
    """
    '의미 단위로 적당히' 한 줄 자막 덩어리로 분할.

    목표:
    - 너무 잘게 쪼개지지 않게(min_chars로 합침)
    - 한 줄이 너무 길어져 2줄로 자동 줄바꿈 되는 걸 줄이기(max_chars)
    - 한 segment에서 자막이 너무 많이 튀지 않게(max_lines_per_segment)
    """
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []

    # 1) 1차 후보: 문장부호/쉼표 기준으로 분할 (의미 단위)
    parts = re.split(r"(?<=[.!?。！？])\s+|(?<=[,，])\s+", text)
    parts = [p.strip() for p in parts if p.strip()]

    # 2) 각 part가 너무 길면 공백 기준으로 max_chars에 맞춰 쪼갬
    raw: List[str] = []
    for p in parts:
        if len(p) <= max_chars:
            raw.append(p)
            continue

        words = p.split(" ")
        if len(words) > 1:
            cur = ""
            for w in words:
                cand = (cur + " " + w).strip() if cur else w
                if len(cand) <= max_chars:
                    cur = cand
                else:
                    if cur:
                        raw.append(cur)
                    cur = w
            if cur:
                raw.append(cur)
        else:
            # 공백 거의 없는 경우 강제 분할
            for i in range(0, len(p), max_chars):
                raw.append(p[i:i + max_chars])

    raw = [" ".join(x.split()) for x in raw if x.strip()]

    # 3) 너무 짧은 조각(min_chars 미만)은 앞/뒤와 합쳐서 “너무 잘게”를 방지
    merged: List[str] = []
    for piece in raw:
        if not merged:
            merged.append(piece)
            continue

        if len(piece) < min_chars:
            # 이전 조각이 너무 길지 않으면 합치기
            if len(merged[-1]) + 1 + len(piece) <= max_chars:
                merged[-1] = f"{merged[-1]} {piece}".strip()
            else:
                merged.append(piece)
        else:
            merged.append(piece)

    # 4) 한 segment당 최대 줄 수 제한 (너무 많이 튀는 것 방지)
    if max_lines_per_segment and len(merged) > max_lines_per_segment:
        # 앞쪽은 유지하고, 나머지는 뒤에서 합쳐서 줄 수를 맞춤
        head = merged[: max_lines_per_segment - 1]
        tail = " ".join(merged[max_lines_per_segment - 1 :])
        # tail도 너무 길면 다시 max_chars로 쪼개지만, 그래도 줄 수는 제한
        tail_chunks = []
        if len(tail) <= max_chars:
            tail_chunks = [tail]
        else:
            words = tail.split(" ")
            cur = ""
            for w in words:
                cand = (cur + " " + w).strip() if cur else w
                if len(cand) <= max_chars:
                    cur = cand
                else:
                    if cur:
                        tail_chunks.append(cur)
                    cur = w
            if cur:
                tail_chunks.append(cur)
            # 줄 수 맞추기: tail_chunks가 여러 개면 다시 합쳐서 1줄로(가능한 범위)
            if len(tail_chunks) > 1:
                # 너무 길어도 일단 1줄 유지가 목표면 합침(길면 플레이어가 2줄로 나눌 수 있음)
                tail_chunks = [" ".join(tail_chunks)]

        merged = head + tail_chunks

    return merged


def segments_to_srt(
    segments: List[Dict],
    *,
    max_chars: int = 26,          # ✅ 여기로 “쪼개짐 정도” 조절 (24~30 추천)
    min_chars: int = 10,          # ✅ 너무 짧은 조각 합치기 (8~12 추천)
    max_lines_per_segment: int = 3,  # ✅ 세그먼트당 최대 3줄(=3개의 1줄 cue)
    min_duration: float = 0.75,   # ✅ 너무 빨리 바뀌지 않게
    max_duration: float = 3.0,    # ✅ 너무 오래 붙지 않게
    gap: float = 0.03,
) -> str:
    """
    - 한 줄씩 순차 출력
    - 너무 잘게 쪼개지 않게(의미 단위 + min_chars 병합)
    - 한 segment에서 2~3번 정도만 교체되도록 제한
    """
    lines: List[str] = []
    idx = 1

    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        text = str(seg.get("text", "")).strip()

        if not text or end <= start:
            continue

        chunks = _split_to_chunks(
            text,
            max_chars=max_chars,
            min_chars=min_chars,
            max_lines_per_segment=max_lines_per_segment,
        )
        if not chunks:
            continue

        total_time = end - start
        weights = [max(1, len(c)) for c in chunks]
        wsum = sum(weights)

        t = start
        for c, w in zip(chunks, weights):
            dur = total_time * (w / wsum)

            if dur < min_duration:
                dur = min_duration
            if dur > max_duration:
                dur = max_duration

            t_end = t + dur
            if t_end > end:
                t_end = end

            lines.append(str(idx))
            lines.append(f"{_fmt_srt_time(t)} --> {_fmt_srt_time(t_end)}")
            lines.append(c)   # ✅ 항상 한 줄
            lines.append("")
            idx += 1

            t = t_end + gap
            if t >= end:
                break

    return "\n".join(lines).strip() + "\n"
