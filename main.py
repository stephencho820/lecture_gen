import sys
from pathlib import Path
from src.transcriber import transcribe_audio
from src.rewriter import rewrite_for_rich_mindset_channel
from src.tts import script_to_speech


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
# MAIN
# -------------------------------------------------------------------
def main():
    """
    사용법:
      python main.py full 01
      python main.py stt 02
      python main.py rewrite 03
      python main.py tts 04
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
        step1_stt(audio_path)
        step2_rewrite(audio_stem)
        step3_tts(audio_stem)
        print("[INFO] 전체 플로우 완료!")

    elif mode == "stt":
        step1_stt(audio_path)
        print("[INFO] STT 완료.")

    elif mode == "rewrite":
        step2_rewrite(audio_stem)
        print("[INFO] 재작성 완료.")

    elif mode == "tts":
        step3_tts(audio_stem)
        print("[INFO] TTS 완료.")

    else:
        print(
            "사용법:\n"
            "  python main.py full [번호]\n"
            "  python main.py stt [번호]\n"
            "  python main.py rewrite [번호]\n"
            "  python main.py tts [번호]\n"
        )


if __name__ == "__main__":
    main()
