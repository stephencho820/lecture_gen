from pathlib import Path
import yt_dlp
from yt_dlp.utils import DownloadError


def download_audio_from_youtube(youtube_url: str, output_dir: str = "downloads") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "noplaylist": True,
        "ignoreerrors": False,
        "quiet": False,
    }

    print("[INFO] 유튜브 오디오(mp3) 다운로드 중...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
    except DownloadError as e:
        raise RuntimeError(
            "이 유튜브 영상은 로그인/봇 방지 등의 이유로 자동 다운로드가 차단된 것 같습니다.\n"
            "다른 공개 영상 URL을 사용하거나, 브라우저에서 직접 mp3를 확보해 주세요."
        ) from e

    mp3_files = list(out_dir.glob("*.mp3"))
    if not mp3_files:
        raise FileNotFoundError("mp3 파일이 생성되지 않았습니다.")

    latest = max(mp3_files, key=lambda f: f.stat().st_mtime)
    print(f"[INFO] 다운로드 완료. 파일: {latest}")
    return latest
