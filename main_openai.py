import sys
from pathlib import Path

from src.transcriber import transcribe_audio
from src.rewriter import rewrite_for_rich_mindset_channel
from src.tts import script_to_speech

# 🔧 여기만 파일명 바꿔가면서 쓰면 됨
INPUT_AUDIO = Path("input_audio/my_lecture_00.mp3")
OUTPUT_DIR = Path("outputs")


def step1_stt(audio_path: Path) -> Path:
    """
    1단계: mp3 -> original.txt (전사만)
    """
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


def step2_rewrite(audio_stem: str | None = None) -> Path:
    """
    2단계: original.txt -> rich_mindset.txt (재작성만)
    - audio_stem이 None이면 INPUT_AUDIO.stem 사용
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    if audio_stem is None:
        audio_stem = INPUT_AUDIO.stem

    original_path = OUTPUT_DIR / f"{audio_stem}_original.txt"
    if not original_path.exists():
        raise FileNotFoundError(
            f"원본 전사본 텍스트 파일을 찾을 수 없습니다: {original_path}\n"
            f"먼저 `python main.py stt` 또는 `python main.py full` 로 전사 단계를 실행해야 합니다."
        )

    print(f"[STEP 2] original.txt -> rich_mindset.txt (재작성)")
    print(f"[INFO] 입력 전사본: {original_path}")

    original_text = original_path.read_text(encoding="utf-8")
    rewritten = rewrite_for_rich_mindset_channel(original_text)

    rewritten_path = OUTPUT_DIR / f"{audio_stem}_rich_mindset.txt"
    rewritten_path.write_text(rewritten, encoding="utf-8")
    print(f"[INFO] 재작성본 저장: {rewritten_path}")

    return rewritten_path


def step3_tts(audio_stem: str | None = None) -> list[Path]:
    """
    3단계: rich_mindset.txt -> TTS(mp3) (음성만)
    - audio_stem이 None이면 INPUT_AUDIO.stem 사용
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    if audio_stem is None:
        audio_stem = INPUT_AUDIO.stem

    rewritten_path = OUTPUT_DIR / f"{audio_stem}_rich_mindset.txt"
    if not rewritten_path.exists():
        raise FileNotFoundError(
            f"재작성본 텍스트 파일을 찾을 수 없습니다: {rewritten_path}\n"
            f"먼저 `python main.py rewrite` 또는 `python main.py full` 로 "
            f"재작성 단계를 실행해야 합니다."
        )

    print(f"[STEP 3] rich_mindset.txt -> TTS")
    print(f"[INFO] 입력 재작성본: {rewritten_path}")

    rewritten_text = rewritten_path.read_text(encoding="utf-8")

    tts_base_path = OUTPUT_DIR / f"{audio_stem}_rich_mindset_ko_male.mp3"
    tts_files = script_to_speech(
        rewritten_text,
        tts_base_path,
        model="gpt-4o-mini-tts",
        voice="onyx",
        instructions="진중한 톤의 한국인 자연스러운 톤으로, 차분하지만 정말 인간이 읽는 것 처럼 때론 감정적으로 읽어 주세요.",
    )

    print("[INFO] 생성된 TTS 파일들:")
    for p in tts_files:
        print(" -", p)

    return tts_files


def main():
    """
    실행 모드:
      python main.py full     -> 1단계 + 2단계 + 3단계 전체 실행
      python main.py stt      -> 1단계만 (mp3 -> original.txt)
      python main.py rewrite  -> 2단계만 (original.txt -> rich_mindset.txt)
      python main.py tts      -> 3단계만 (rich_mindset.txt -> TTS)
    """
    mode = "full"
    if len(sys.argv) >= 2:
        mode = sys.argv[1].strip().lower()

    print(f"[INFO] 실행 모드: {mode}")

    if mode == "full":
        # 1단계
        original_path = step1_stt(INPUT_AUDIO)
        # 2단계
        rewritten_path = step2_rewrite(INPUT_AUDIO.stem)
        # 3단계
        _ = step3_tts(INPUT_AUDIO.stem)
        print("[INFO] 전체 플로우 완료! (mp3 -> text -> new text -> TTS)")

    elif mode == "stt":
        _ = step1_stt(INPUT_AUDIO)
        print("[INFO] 1단계(STT)만 완료. (mp3 -> original.txt)")

    elif mode == "rewrite":
        _ = step2_rewrite(INPUT_AUDIO.stem)
        print("[INFO] 2단계(재작성)만 완료. (original.txt -> rich_mindset.txt)")

    elif mode == "tts":
        _ = step3_tts(INPUT_AUDIO.stem)
        print("[INFO] 3단계(TTS)만 완료. (rich_mindset.txt -> mp3)")

    else:
        print(
            "사용법:\n"
            "  python main.py full     -> mp3 -> text -> new text -> TTS (전체)\n"
            "  python main.py stt      -> mp3 -> original.txt 까지만 실행\n"
            "  python main.py rewrite  -> original.txt -> rich_mindset.txt 만 실행\n"
            "  python main.py tts      -> rich_mindset.txt -> TTS 만 실행\n"
        )


if __name__ == "__main__":
    main()
