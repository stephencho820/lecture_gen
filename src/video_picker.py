import random
from pathlib import Path

CATEGORY_KEYWORDS = {
    # 1️⃣ 거시·정책·환율 (가장 많이 나와야 함)
    "economy": [
        "환율", "달러", "금리", "경제", "시장", "증시",
        "주식", "해외주식", "국내주식",
        "정책", "정부", "세금", "양도소득세",
        "자금", "유입", "유출", "외환", "선물환"
    ],

    # 2️⃣ 일·투자 판단·전략
    "work": [
        "투자", "전략", "리스크", "판단",
        "포트폴리오", "분산", "매수", "매도",
        "수익", "손실",
        "결정", "신중", "선택"
    ],

    # 3️⃣ 개인 투자자 관점
    "people": [
        "투자자", "개인", "여러분", "본인",
        "직장인", "사람", "선택", "성향"
    ],

    # 4️⃣ 사회·국가 맥락
    "city": [
        "한국", "국내", "국가", "사회",
        "증권사", "은행", "시장 전체"
    ],

    # 5️⃣ 불안·위기·경고 톤
    "night": [
        "불안", "위기", "조급", "걱정",
        "급락", "변동성", "흔들림"
    ],
}

# fallback 우선순위 (없을 때 이 순서로 시도)
FALLBACK_ORDER = ["abstract", "city", "night"]

def pick_category(scene_text: str) -> str:
    if not scene_text:
        return "abstract"

    for category, keywords in CATEGORY_KEYWORDS.items():
        for k in keywords:
            if k in scene_text:
                return category

    return "abstract"

def pick_stock_video(scene_text: str, stock_root: Path) -> Path:
    category = pick_category(scene_text)
    print("🧠 CATEGORY =", repr(category))
    print("📂 LOOKING FOR =", stock_root / category)
    # 1️⃣ 1차 시도: 매칭된 카테고리
    candidates = list((stock_root / category).glob("*.mp4"))

    # 2️⃣ fallback 순회
    if not candidates:
        for fb in FALLBACK_ORDER:
            candidates = list((stock_root / fb).glob("*.mp4"))
            if candidates:
                break

    if not candidates:
        raise FileNotFoundError(
            f"사용 가능한 스톡 영상이 없습니다. "
            f"확인 필요: {stock_root}"
        )

    return random.choice(candidates)
