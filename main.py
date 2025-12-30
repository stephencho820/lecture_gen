import sys
import json
from pathlib import Path
from glob import glob

from src.transcriber import transcribe_audio
from src.rewriter import rewrite_for_rich_mindset_channel

from src.transcriber_timestamped import transcribe_parts_timestamped
from src.subtitles import segments_to_srt
from src.scene_planner import (
    load_timestamped_json,
    build_scenes_from_segments,
    save_scene_plan,
)
from src.prompt_generator import fill_scene_prompts
from src.video_renderer import (
    render_scene_clips_from_videos,
    concat_audio_mp3,
    concat_video_clips,
    mux_final,
)

# -------------------------------------------------------------------
# utils
# -------------------------------------------------------------------
OUTPUT_DIR = Path("outputs")


def safe_unlink(path: Path):
    try:
        if path.exists():
            path.unlink()
            print(f"[CLEANUP] 삭제: {path}")
    except Exception as e:
        print(f"[WARN] 파일 삭제 실패: {path} ({e})")


def safe_rmtree(dir_path: Path):
    try:
        if dir_path.exists() and dir_path.is_dir():
            for p in dir_path.rglob("*"):
                if p.is_file():
                    p.unlink()
            dir_path.rmdir()
            print(f"[CLEANUP] 디렉토리 삭제: {dir_path}")
    except Exception as e:
        print(f"[WARN] 디렉토리 삭제 실패: {dir_path} ({e})")


def get_audio_paths(number: str | None):
    if number is None:
        number = "00"
    number = number.zfill(2)

    audio_path = Path("input_audio") / f"my_lecture_{number}.mp3"
    audio_stem = audio_path.stem
    return audio_path, audio_stem


# -------------------------------------------------------------------
# STEP 1 – STT
# -------------------------------------------------------------------
def step1_stt(audio_path: Path) -> Path:
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    text = transcribe_audio(audio_path)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / f"{audio_path.stem}_original.txt"
    out.write_text(text, encoding="utf-8")

    print(f"[DONE] STT → {out}")
    return out


# -------------------------------------------------------------------
# STEP 2 – Rewrite
# -------------------------------------------------------------------
def step2_rewrite(audio_stem: str) -> Path:
    src = OUTPUT_DIR / f"{audio_stem}_original.txt"
    if not src.exists():
        raise FileNotFoundError(src)

    rewritten = rewrite_for_rich_mindset_channel(src.read_text(encoding="utf-8"))
    out = OUTPUT_DIR / f"{audio_stem}_rich_mindset.txt"
    out.write_text(rewritten, encoding="utf-8")

    print(f"[DONE] Rewrite → {out}")
    return out


# -------------------------------------------------------------------
# STEP 3 – TTS (Codespaces)
# -------------------------------------------------------------------
def step3_tts(audio_stem: str):
    from src.tts import script_to_speech

    src = OUTPUT_DIR / f"{audio_stem}_rich_mindset.txt"
    if not src.exists():
        raise FileNotFoundError(src)

    script_to_speech(
        src.read_text(encoding="utf-8"),
        OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male",
        emotion_preset="normal",
        emotion_intensity=0.8,
        volume=110,
        audio_pitch=-1,
        audio_tempo=1.0,
        audio_format="mp3",
    )

    print("[DONE] TTS 완료 (Codespaces)")


# -------------------------------------------------------------------
# AFTER TTS PIPELINE (Termux)
# -------------------------------------------------------------------
def after_tts_pipeline(audio_stem: str):
    pattern = str(OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male*part*.mp3")
    parts = sorted([Path(p) for p in glob(pattern)])

    if not parts:
        raise RuntimeError(
            "TTS 결과 mp3가 없습니다.\n"
            "→ Codespaces에서 `python main.py tts` 실행 후 git sync 하세요."
        )

    merged = transcribe_parts_timestamped(parts, language="ko")

    ts_json = OUTPUT_DIR / f"{audio_stem}_timestamped.json"
    ts_json.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    srt = OUTPUT_DIR / f"{audio_stem}.srt"
    srt.write_text(segments_to_srt(merged["segments"]), encoding="utf-8")

    for p in parts:
        safe_unlink(p)

    scenes = build_scenes_from_segments(
        merged["segments"],
        target_sec=13.0,
        min_sec=8.0,
        max_sec=18.0,
        max_chars=240,
    )

    scene_plan = OUTPUT_DIR / f"{audio_stem}_scene_plan.json"
    save_scene_plan(scenes, scene_plan, source_timestamped=ts_json.name)

    filled = fill_scene_prompts(scene_plan)

    narration = OUTPUT_DIR / f"{audio_stem}_narration.mp3"
    concat_audio_mp3(
        sorted(OUTPUT_DIR.glob(f"{audio_stem}_rich_mindset_ko_male*.mp3")),
        narration,
    )

    clips_dir = OUTPUT_DIR / f"{audio_stem}_clips"
    clips = render_scene_clips_from_videos(
        filled, OUTPUT_DIR / "stock_videos", clips_dir
    )

    video = OUTPUT_DIR / f"{audio_stem}_video.mp4"
    concat_video_clips(clips, video)

    final = OUTPUT_DIR / f"{audio_stem}_final.mp4"
    mux_final(video, narration, final, subtitles_srt=srt, burn_subtitles=True)

    safe_unlink(video)
    safe_unlink(narration)
    safe_rmtree(clips_dir)

    print(f"[DONE] after_tts 파이프라인 완료 → {final}")


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def main():
    mode = sys.argv[1] if len(sys.argv) >= 2 else None
    number = sys.argv[2] if len(sys.argv) >= 3 else None

    audio_path, audio_stem = get_audio_paths(number)

    if mode == "stt_rewrite":
        step1_stt(audio_path)
        step2_rewrite(audio_stem)

    elif mode == "tts":
        step3_tts(audio_stem)

    elif mode == "after_tts":
        after_tts_pipeline(audio_stem)

    else:
        print(
            """
사용법:

[Termux]
  python main.py stt_rewrite 01
  python main.py after_tts 01

[Codespaces]
  python main.py tts 01
"""
        )


if __name__ == "__main__":
    main()
