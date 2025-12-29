import sys
from pathlib import Path
from src.transcriber import transcribe_audio
from src.rewriter import rewrite_for_rich_mindset_channel
from src.tts import script_to_speech
from src.thumbnail import make_thumbnail

from glob import glob
import json
from src.transcriber_timestamped import transcribe_parts_timestamped
from src.subtitles import segments_to_srt
from src.scene_planner import load_timestamped_json, build_scenes_from_segments, save_scene_plan
from src.prompt_generator import fill_scene_prompts
from glob import glob
# from src.video_renderer import (
#     generate_scene_images,
#     concat_audio_mp3,
#     render_scene_clips,
#     concat_video_clips,
#     mux_final,
# )
from src.video_renderer import (
    render_scene_clips_from_videos,
    concat_audio_mp3,
    concat_video_clips,
    mux_final,
)



# -------------------------------------------------------------------
# 🔧 파일 번호 선택 기능 추가
# -------------------------------------------------------------------
def get_audio_paths(number: str | None):
    """
    number = "01", "02" 등 두 자리 문자열
    number가 없으면 기본값 "00"
    """
    if number is None:
        number = "00"

    # zero-padding 보장
    number = number.zfill(2)

    audio_filename = f"my_lecture_{number}.mp3"
    audio_path = Path("input_audio") / audio_filename
    audio_stem = audio_path.stem  # my_lecture_01

    return audio_path, audio_stem


OUTPUT_DIR = Path("outputs")


# -------------------------------------------------------------------
# 1단계
# -------------------------------------------------------------------
def step1_stt(audio_path: Path) -> Path:
    if not audio_path.exists():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_path}")

    print(f"[STEP 1] mp3 -> text (STT)")
    print(f"[INFO] 입력 오디오 파일: {audio_path}")

    transcript = transcribe_audio(audio_path)

    OUTPUT_DIR.mkdir(exist_ok=True)
    original_path = OUTPUT_DIR / f"{audio_path.stem}_original.txt"
    original_path.write_text(transcript, encoding="utf-8")

    print(f"[INFO] 전사본 저장: {original_path}")
    return original_path


# -------------------------------------------------------------------
# 2단계
# -------------------------------------------------------------------
def step2_rewrite(audio_stem: str) -> Path:
    original_path = OUTPUT_DIR / f"{audio_stem}_original.txt"

    if not original_path.exists():
        raise FileNotFoundError(
            f"원본 전사본 텍스트 파일을 찾을 수 없습니다: {original_path}\n"
            f"먼저 STT 단계를 실행해야 합니다."
        )

    print(f"[STEP 2] original.txt -> rich_mindset.txt (재작성)")
    print(f"[INFO] 입력 전사본: {original_path}")

    original_text = original_path.read_text(encoding="utf-8")
    rewritten = rewrite_for_rich_mindset_channel(original_text)

    rewritten_path = OUTPUT_DIR / f"{audio_stem}_rich_mindset.txt"
    rewritten_path.write_text(rewritten, encoding="utf-8")

    print(f"[INFO] 재작성본 저장: {rewritten_path}")
    return rewritten_path


# -------------------------------------------------------------------
# 3단계
# -------------------------------------------------------------------
def step3_tts(audio_stem: str) -> list[Path]:
    rewritten_path = OUTPUT_DIR / f"{audio_stem}_rich_mindset.txt"

    if not rewritten_path.exists():
        raise FileNotFoundError(
            f"재작성본 텍스트 파일을 찾을 수 없습니다: {rewritten_path}\n"
            f"먼저 rewrite 단계를 실행해야 합니다."
        )

    print(f"[STEP 3] rich_mindset.txt -> Typecast TTS")
    print(f"[INFO] 입력 재작성본: {rewritten_path}")

    rewritten_text = rewritten_path.read_text(encoding="utf-8")
    tts_base_path = OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male"

    tts_files = script_to_speech(
        rewritten_text,
        tts_base_path,
        emotion_preset="normal",
        emotion_intensity=0.8,
        volume=110,
        audio_pitch=-1,
        audio_tempo=1.0,
        audio_format="mp3",
    )

    print("[INFO] 생성된 TTS 파일들:")
    for p in tts_files:
        print(" -", p)

    return tts_files

# -------------------------------------------------------------------
# 4단계
# -------------------------------------------------------------------
def step4_timestamp_stt_from_tts(audio_stem: str) -> tuple[Path, Path]:
    """
    outputs/ 아래의 my_lecture_00_rich_mindset_ko_male_part1/2/3.mp3를 찾아
    timestamp 전사(json) + srt 생성
    """
    print("[STEP 4] TTS mp3(part1~n) -> timestamp transcript(json) + subtitles(srt)")

    # 예: outputs/my_lecture_00_rich_mindset_ko_male_part1.mp3
    pattern = str(OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male_part*.mp3")
    part_paths = sorted([Path(p) for p in glob(pattern)])

    if not part_paths:
        # Typecast 코드가 __part1 형태로 만들 수도 있어서 fallback
        pattern2 = str(OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male__part*.mp3")
        part_paths = sorted([Path(p) for p in glob(pattern2)])

    if not part_paths:
        raise FileNotFoundError(
            f"TTS part mp3를 찾지 못했습니다.\n"
            f"- 기대 패턴: {pattern}\n"
            f"- 또는: {pattern2}\n"
            f"먼저 TTS 단계를 실행해야 합니다."
        )

    print("[INFO] 감지된 TTS 파트들:")
    for p in part_paths:
        print(" -", p.name)

    merged = transcribe_parts_timestamped(part_paths, language="ko")

    json_path = OUTPUT_DIR / f"{audio_stem}_timestamped.json"
    json_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INFO] timestamp JSON 저장: {json_path}")

    srt_text = segments_to_srt(merged["segments"])
    srt_path = OUTPUT_DIR / f"{audio_stem}.srt"
    srt_path.write_text(srt_text, encoding="utf-8")
    print(f"[INFO] SRT 저장: {srt_path}")

    return json_path, srt_path

# -------------------------------------------------------------------
# 5단계
# -------------------------------------------------------------------
def step5_build_scene_plan(audio_stem: str) -> Path:
    print("[STEP 5] timestamped.json -> scene_plan.json (장면 분할)")
    ts_path = OUTPUT_DIR / f"{audio_stem}_timestamped.json"
    if not ts_path.exists():
        raise FileNotFoundError(
            f"timestamped.json이 없습니다: {ts_path}\n먼저 stt_ts를 실행하세요."
        )

    data = load_timestamped_json(ts_path)
    segments = data["segments"]

    scenes = build_scenes_from_segments(
        segments,
        target_sec=13.0,   # 추천: 10분이면 40~55 scene 정도
        min_sec=8.0,
        max_sec=18.0,
        max_chars=240,
    )

    out_path = OUTPUT_DIR / f"{audio_stem}_scene_plan.json"
    save_scene_plan(scenes, out_path, source_timestamped=str(ts_path.name))
    print(f"[INFO] scene_plan 저장: {out_path} (scenes={len(scenes)})")
    return out_path

# -------------------------------------------------------------------
# 6단계
# -------------------------------------------------------------------
def step6_fill_prompts(audio_stem: str) -> Path:
    print("[STEP 6] scene_plan.json -> scene_plan_filled.json (프롬프트 자동 생성)")
    sp_path = OUTPUT_DIR / f"{audio_stem}_scene_plan.json"
    if not sp_path.exists():
        raise FileNotFoundError(f"scene_plan.json이 없습니다: {sp_path}\n먼저 scene_plan을 생성하세요.")
    return fill_scene_prompts(sp_path, overwrite=False)

# -------------------------------------------------------------------
# 7단계
# -------------------------------------------------------------------

def step7_render_video(audio_stem: str) -> Path:
    print("[STEP 7] stock videos + ffmpeg 합성 (오디오 concat 포함)")

    filled_path = OUTPUT_DIR / f"{audio_stem}_scene_plan_filled.json"
    if not filled_path.exists():
        raise FileNotFoundError(
            f"scene_plan_filled.json이 없습니다: {filled_path}\n먼저 prompts를 실행하세요."
        )

    # ------------------------------------------------------------------
    # 1) 오디오 concat
    # ------------------------------------------------------------------
    pattern = str(OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male__part*.mp3")
    audio_parts = sorted([Path(p) for p in glob(pattern)])
    if not audio_parts:
        pattern2 = str(OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male_part*.mp3")
        audio_parts = sorted([Path(p) for p in glob(pattern2)])

    if not audio_parts:
        raise FileNotFoundError("TTS part mp3를 찾지 못했습니다. outputs 폴더를 확인하세요.")

    narration_path = OUTPUT_DIR / f"{audio_stem}_narration.mp3"
    concat_audio_mp3(audio_parts, narration_path)

    # ------------------------------------------------------------------
    # 2) 장면별 클립 생성 (스톡 영상 기반)
    # ------------------------------------------------------------------
    stock_root = OUTPUT_DIR / "stock_videos"
    clips_dir = OUTPUT_DIR / f"{audio_stem}_clips"

    clips = render_scene_clips_from_videos(
        filled_path,
        stock_root,
        clips_dir,
        overwrite=False,
    )

    # ------------------------------------------------------------------
    # 3) 클립 concat
    # ------------------------------------------------------------------
    video_path = OUTPUT_DIR / f"{audio_stem}_video.mp4"
    concat_video_clips(clips, video_path)

    # ------------------------------------------------------------------
    # 4) 최종 mux (+ 자막)
    # ------------------------------------------------------------------
    srt_path = OUTPUT_DIR / f"{audio_stem}.srt"
    final_path = OUTPUT_DIR / f"{audio_stem}_final.mp4"

    mux_final(
        video_path,
        narration_path,
        final_path,
        subtitles_srt=srt_path if srt_path.exists() else None,
        burn_subtitles=True,
    )
    

    print(f"[DONE] final: {final_path}")
    return final_path

# def step7_render_video(audio_stem: str) -> Path:
#     print("[STEP 7] images + ffmpeg 합성 (오디오 concat 포함)")

#     filled_path = OUTPUT_DIR / f"{audio_stem}_scene_plan_filled.json"
#     if not filled_path.exists():
#         raise FileNotFoundError(f"scene_plan_filled.json이 없습니다: {filled_path}\n먼저 prompts를 실행하세요.")

#     # 1) 이미지 생성
#     # images_dir = OUTPUT_DIR / f"{audio_stem}_images"
#     # generate_scene_images(
#     #     filled_path,
#     #     images_dir,
#     #     size="1792x1024",   # ✅ 강제 지정
#     #     overwrite=False,
#     # )

#     # 2) 오디오 concat
#     pattern = str(OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male__part*.mp3")
#     audio_parts = sorted([Path(p) for p in glob(pattern)])
#     if not audio_parts:
#         # 혹시 part1 형태면 fallback
#         pattern2 = str(OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male_part*.mp3")
#         audio_parts = sorted([Path(p) for p in glob(pattern2)])

#     if not audio_parts:
#         raise FileNotFoundError("TTS part mp3를 찾지 못했습니다. outputs 폴더를 확인하세요.")

#     narration_path = OUTPUT_DIR / f"{audio_stem}_narration.mp3"
#     concat_audio_mp3(audio_parts, narration_path)

#     # 3) 장면별 클립 생성
#     # clips_dir = OUTPUT_DIR / f"{audio_stem}_clips"
#     # clips = render_scene_clips(
#     #     filled_path,
#     #     images_dir,
#     #     clips_dir,
#     #     overwrite=False,
#     # )

#     # 4) 클립 concat
#     video_path = OUTPUT_DIR / f"{audio_stem}_video.mp4"
#     concat_video_clips(clips, video_path)

#     # 5) 최종 mux (+ 자막)
#     srt_path = OUTPUT_DIR / f"{audio_stem}.srt"
#     final_path = OUTPUT_DIR / f"{audio_stem}_final.mp4"
#     mux_final(
#         video_path,
#         narration_path,
#         final_path,
#         subtitles_srt=srt_path if srt_path.exists() else None,
#         burn_subtitles=False,   # 원하면 True로 바꾸면 자막 “번인”
#     )

#     print(f"[DONE] final: {final_path}")
#     return final_path
# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def main():
    """
    사용법:
      python main.py full 01   # ✅ 1~7단계 전체 실행
      python main.py stt 02
      python main.py rewrite 03
      python main.py tts 04
      python main.py stt_ts 04
      python main.py scene_plan 04
      python main.py prompts 04
      python main.py render 04
    """
    mode = "full"
    number = None

    if len(sys.argv) >= 2:
        mode = sys.argv[1].strip().lower()

    if len(sys.argv) >= 3:
        number = sys.argv[2].strip()

    # 파일 경로 생성
    audio_path, audio_stem = get_audio_paths(number)

    print(f"[INFO] 실행 모드: {mode}")
    print(f"[INFO] 선택된 파일: {audio_path}")

    if mode == "full":
        # 1) STT
        step1_stt(audio_path)

        # 2) Rewrite
        step2_rewrite(audio_stem)

        # 3) TTS
        step3_tts(audio_stem)

        # 4) Timestamp STT + SRT
        step4_timestamp_stt_from_tts(audio_stem)

        # 5) Scene plan
        step5_build_scene_plan(audio_stem)

        # 6) Prompt fill
        step6_fill_prompts(audio_stem)

        # 7) Render final video
        step7_render_video(audio_stem)

        print("[INFO] 전체 플로우(1~7) 완료!")

    elif mode == "stt":
        step1_stt(audio_path)
        print("[INFO] STT 완료.")

    elif mode == "rewrite":
        step2_rewrite(audio_stem)
        print("[INFO] 재작성 완료.")

    elif mode == "tts":
        step3_tts(audio_stem)
        print("[INFO] TTS 완료.")

    elif mode == "stt_ts":
        step4_timestamp_stt_from_tts(audio_stem)
        print("[INFO] timestamp STT 완료.")

    elif mode == "scene_plan":
        step5_build_scene_plan(audio_stem)
        print("[INFO] scene_plan 생성 완료.")

    elif mode == "prompts":
        step6_fill_prompts(audio_stem)
        print("[INFO] 프롬프트 생성 완료.")

    elif mode == "render":
        step7_render_video(audio_stem)
        print("[INFO] 렌더 완료.")

    elif mode == "thumbnail":
        print("썸네일에 들어갈 문구를 입력하세요 (1~2줄):")

        lines = []
        while len(lines) < 2:
            line = input()
            if line.strip() == "":
                break
            lines.append(line)

        text = "\n".join(lines)

        out = make_thumbnail(audio_stem, text)
        print(f"[DONE] 썸네일 생성: {out}")


    else:
        print(
            "사용법:\n"
            "  python main.py full [번호]\n"
            "  python main.py stt [번호]\n"
            "  python main.py rewrite [번호]\n"
            "  python main.py tts [번호]\n"
            "  python main.py stt_ts [번호]\n"
            "  python main.py scene_plan [번호]\n"
            "  python main.py prompts [번호]\n"
            "  python main.py render [번호]\n"
        )

if __name__ == "__main__":
    main()
