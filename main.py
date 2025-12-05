from pathlib import Path

from src.downloader import download_audio_from_youtube
from src.transcriber import transcribe_audio
from src.rewriter import rewrite_for_rich_mindset_channel
from src.tts import script_to_speech


def build_my_lecture(youtube_url: str):
    # 1) 유튜브 오디오 다운로드
    audio_file = download_audio_from_youtube(youtube_url)

    # 2) 음성 → 텍스트 전사
    transcript = transcribe_audio(audio_file)

    outputs = Path("outputs")
    outputs.mkdir(exist_ok=True)

    # 2-1) 전사본 저장
    original_path = outputs / (audio_file.stem + "_original.txt")
    original_path.write_text(transcript, encoding="utf-8")
    print(f"[INFO] 전사본 저장: {original_path}")

    # 3) '부자의 사고법' 스타일 재작성
    rewritten = rewrite_for_rich_mindset_channel(transcript)

    rewritten_path = outputs / (audio_file.stem + "_rich_mindset.txt")
    rewritten_path.write_text(rewritten, encoding="utf-8")
    print(f"[INFO] 재작성본 저장: {rewritten_path}")

    # 4) 재작성 스크립트를 TTS로 오디오로 변환
    # ⚠️ Audio API는 input 최대 4096자 제한이 있으니,
    #    실제로 스크립트가 길어지면 나중에 섹션별로 나눠서 TTS 돌리는 걸 추천.
    audio_output_path = outputs / (audio_file.stem + "_rich_mindset_ko_male.mp3")
    script_to_speech(
        rewritten,
        audio_output_path,
        model="gpt-4o-mini-tts",
        voice="onyx",  # 진중한 남성 톤에 어울리는 보이스 후보
        instructions="낮은 톤의 진중한 한국인 남성 강의 톤으로, 차분하고 또박또박 읽어 주세요.",
    )

    print("[INFO] 전체 플로우 완료!")


if __name__ == "__main__":
    # 👉 여기만 바꾸면 됨
    YOUTUBE_URL = "https://www.youtube.com/watch?v=영상ID"
    build_my_lecture(YOUTUBE_URL)
