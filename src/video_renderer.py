# src/video_renderer.py
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

# -------------------------------------------------------------------
# ⚠️ 이미지 생성(DALL·E) 완전 비활성
# -------------------------------------------------------------------
ENABLE_IMAGE_GEN = False  # 절대 True로 하지 마세요 (비용 발생)

# -------------------------------------------------------------------
# 내부 유틸
# -------------------------------------------------------------------
def _run(cmd: list[str]) -> None:
    print("[CMD]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg가 설치되어 있지 않습니다.")


def load_scene_plan(scene_plan_filled_path: Path) -> Dict[str, Any]:
    data = json.loads(scene_plan_filled_path.read_text(encoding="utf-8"))
    if "scenes" not in data:
        raise ValueError("scene_plan_filled.json에 scenes가 없습니다.")
    return data


# -------------------------------------------------------------------
# ❌ 이미지 생성 (완전 차단)
# -------------------------------------------------------------------
def generate_scene_images(*args, **kwargs):
    raise RuntimeError(
        "이미지 생성(DALL·E)은 비활성화되어 있습니다.\n"
        "스톡 영상 방식을 사용하세요."
    )


# -------------------------------------------------------------------
# 1) 오디오 concat
# -------------------------------------------------------------------
def concat_audio_mp3(audio_parts: List[Path], out_path: Path) -> Path:
    _ensure_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lst = out_path.parent / "audio_concat_list.txt"
    lines = [f"file '{p.resolve()}'" for p in audio_parts]
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(lst),
            "-c", "copy",
            str(out_path),
        ])
    except subprocess.CalledProcessError:
        _run([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(lst),
            "-c:a", "libmp3lame", "-q:a", "2",
            str(out_path),
        ])

    return out_path


# -------------------------------------------------------------------
# 2) 장면별 클립 생성 (스톡 영상 기반)
# -------------------------------------------------------------------
def render_scene_clips_from_videos(
    scene_plan_filled_path: Path,
    stock_root: Path,
    clips_dir: Path,
    *,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
    overwrite: bool = False,
) -> List[Path]:
    """
    keywords → script → image_prompt 순으로 매칭하여
    스톡 영상(mp4)을 선택하고 duration만큼 clip 생성
    """
    _ensure_ffmpeg()
    clips_dir.mkdir(parents=True, exist_ok=True)

    from src.video_picker import pick_stock_video

    data = load_scene_plan(scene_plan_filled_path)
    scenes = data["scenes"]

    out_paths: List[Path] = []

    for s in scenes:
        scene_id = int(s["id"])
        dur = float(s["duration"])

        # ------------------------------------------------------------------
        # ✅ 핵심 로직: 키워드 우선 → 문장 fallback
        # ------------------------------------------------------------------
        keywords_text = ""
        if isinstance(s.get("keywords"), list):
            keywords_text = " ".join(s["keywords"])

        script_text = s.get("script", "")
        prompt_text = s.get("image_prompt", "")

        # 🔥 최종 매칭 텍스트
        match_text = f"{keywords_text} {script_text}".strip()

        # (혹시 script까지 비어있을 경우 최후 fallback)
        if not match_text:
            match_text = prompt_text

        video_path = pick_stock_video(match_text, stock_root)

        if not video_path.exists():
            raise FileNotFoundError(f"스톡 영상이 없습니다: {video_path}")

        clip_path = clips_dir / f"clip_{scene_id:04d}.mp4"
        out_paths.append(clip_path)

        if clip_path.exists() and not overwrite:
            print(f"[SKIP] clip exists: {clip_path.name}")
            continue

        print(f"[VIDEO] scene {scene_id} <- {video_path.parent.name}/{video_path.name}")

        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps},"
            f"format=yuv420p"
        )

        _run([
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(video_path),
            "-t", f"{dur:.3f}",
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            str(clip_path),
        ])

    return out_paths


# -------------------------------------------------------------------
# 3) 클립 concat (무음 영상)
# -------------------------------------------------------------------
def concat_video_clips(clips: List[Path], out_path: Path) -> Path:
    _ensure_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lst = out_path.parent / "video_concat_list.txt"
    lines = [f"file '{p.resolve()}'" for p in clips]
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(lst),
        "-c", "copy",
        str(out_path),
    ])

    return out_path


# -------------------------------------------------------------------
# 4) 최종 mux (영상 + 오디오 + 자막)
# -------------------------------------------------------------------
def mux_final(
    video_path: Path,
    audio_path: Path,
    out_path: Path,
    *,
    subtitles_srt: Path | None = None,
    burn_subtitles: bool = True,
    subtitle_style: str = "Fontsize=22,Outline=1,Shadow=1,MarginV=20",
) -> Path:
    _ensure_ffmpeg()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if subtitles_srt and burn_subtitles:
        sub = subtitles_srt.resolve().as_posix()
        vf = f"subtitles='{sub}':force_style='{subtitle_style}'"

        _run([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out_path),
        ])
        return out_path

    if subtitles_srt and not burn_subtitles:
        _run([
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-i", str(subtitles_srt),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-c:s", "mov_text",
            "-shortest",
            str(out_path),
        ])
        return out_path

    _run([
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out_path),
    ])
    return out_path
