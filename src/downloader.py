import subprocess
from pathlib import Path


def download_audio_from_youtube(youtube_url: str, output_dir: str = "downloads") -> Path:
    """
    yt-dlp를 사용해 유튜브 영상에서 오디오(mp3)만 추출.

    :param youtube_url: 유튜브 영상 URL
    :param output_dir: mp3 저장 폴더
    :return: 가장 최근에 생성된 mp3 파일 경로
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "yt-dlp",
        "-x",                      # 오디오만 추출
        "--audio-format", "mp3",   # mp3로 변환
        "-o", str(out_dir / "%(title)s.%(ext)s"),
        youtube_url,
    ]

    print("[INFO] 유튜브 오디오 다운로드 중...")
    subprocess.run(cmd, check=True)
    print("[INFO] 유튜브 오디오 다운로드 완료")

    mp3_files = list(out_dir.glob("*.mp3"))
    if not mp3_files:
        raise FileNotFoundError("mp3 파일이 없습니다. yt-dlp 설정을 확인하세요.")

    latest = max(mp3_files, key=lambda f: f.stat().st_mtime)
    print(f"[INFO] 사용 오디오 파일: {latest}")
    return latest
