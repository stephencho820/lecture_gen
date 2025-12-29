from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap
import subprocess
import random
import shutil

OUTPUT_DIR = Path("outputs")


# -------------------------------------------------------------------
# 스톡 영상에서 썸네일용 프레임 추출
# -------------------------------------------------------------------
def extract_frame_from_stock(stock_root: Path, out_img: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg가 설치되어 있어야 썸네일을 생성할 수 있습니다.")

    candidates = list(stock_root.rglob("*.mp4"))
    if not candidates:
        raise FileNotFoundError("썸네일용 스톡 영상(mp4)을 찾지 못했습니다.")

    video = random.choice(candidates)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video),
        "-ss", "00:00:01",
        "-vframes", "1",
        "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
        str(out_img),
    ]

    subprocess.run(cmd, check=True)
    print(f"[THUMBNAIL] frame extracted from {video.name}")
    return out_img


# -------------------------------------------------------------------
# 폰트 로딩 (기존 그대로)
# -------------------------------------------------------------------
def load_bold_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        ("ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
        ("ttf", "/usr/share/fonts/truetype/nanum/NanumGothicExtraBold.ttf", None),
        ("ttf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", None),
        ("ttf", "fonts/NanumGothic-Bold.ttf", None),
    ]

    for kind, p, idx in candidates:
        try:
            if Path(p).exists():
                if kind == "ttc":
                    return ImageFont.truetype(p, size, index=idx)
                else:
                    return ImageFont.truetype(p, size)
        except Exception:
            pass

    return ImageFont.load_default()


def wrap_two_lines(text: str, draw, font, max_width: int):
    text = text.strip()

    if "\n" in text:
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        return (parts + ["", ""])[:2]

    approx = max(8, len(text) // 2)
    wrapped = textwrap.wrap(text, width=approx)

    if len(wrapped) == 1:
        return wrapped[0], ""

    line1 = wrapped[0]
    line2 = " ".join(wrapped[1:])

    while draw.textlength(line2, font=font) > max_width and len(line2) > 1:
        line2 = line2[:-1]

    return line1, line2


# -------------------------------------------------------------------
# 메인 썸네일 생성
# -------------------------------------------------------------------
def make_thumbnail(audio_stem: str, text: str) -> Path:
    stock_root = OUTPUT_DIR / "stock_videos"
    base_img_path = OUTPUT_DIR / f"{audio_stem}_thumb_base.jpg"

    extract_frame_from_stock(stock_root, base_img_path)

    img = Image.open(base_img_path).convert("RGBA")
    W, H = img.size

    # 하단 박스
    box_h = int(H * 0.35)
    box_y = H - box_h

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([(0, box_y), (W, H)], fill=(0, 0, 0, 230))

    pad_x = int(W * 0.05)
    max_w = W - pad_x * 2

    font_size = int(H * 0.30)
    tmp_draw = ImageDraw.Draw(img)

    while True:
        font = load_bold_font(font_size)
        line1, line2 = wrap_two_lines(text, tmp_draw, font, max_w)

        h1 = tmp_draw.textbbox((0, 0), line1, font=font)[3]
        h2 = tmp_draw.textbbox((0, 0), line2, font=font)[3] if line2 else 0
        total = h1 + h2 + int(font_size * 0.20)

        if total <= box_h * 0.95 or font_size < 40:
            break
        font_size = int(font_size * 0.95)

    y = box_y + (box_h - total) // 2

    def cx(t):
        return int((W - tmp_draw.textlength(t, font=font)) / 2)

    draw.text((cx(line1), y), line1, font=font, fill=(255, 255, 255, 255))
    if line2:
        draw.text(
            (cx(line2), y + h1 + int(font_size * 0.15)),
            line2,
            font=font,
            fill=(255, 215, 0, 255),
        )

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out = out.resize((1280, 720), Image.LANCZOS)

    out_path = OUTPUT_DIR / f"{audio_stem}_thumbnail.jpg"
    out.save(out_path, "JPEG", quality=90, optimize=True)

    print(f"[DONE] thumbnail saved: {out_path}")
    return out_path
