# Rich Mindset Lecture Builder

유튜브 강의를 기반으로:

1. 오디오 다운로드
2. 텍스트 전사 (Speech-to-Text)
3. '부자의 사고법' 스타일로 스크립트 재작성
4. 재작성된 스크립트를 TTS로 다시 오디오로 생성

까지 한 번에 처리하는 파이썬 프로젝트입니다.

## 구조

```bash
rich-mindset-lecture-builder/
├── .env
├── requirements.txt
├── README.md
├── main.py
├── src/
│   ├── __init__.py
│   ├── downloader.py
│   ├── transcriber.py
│   ├── rewriter.py
│   └── tts.py
├── downloads/
└── outputs/
```

## 준비

1. 패키지 설치

```bash
pip install -r requirements.txt
```

2. `.env` 파일 생성

```env
OPENAI_API_KEY=sk-...
```

3. `main.py` 에 유튜브 링크 넣기

```python
if __name__ == "__main__":
    YOUTUBE_URL = "https://www.youtube.com/watch?v=영상ID"
    build_my_lecture(YOUTUBE_URL)
```

## 실행

```bash
python main.py
```

## 결과

* `outputs/XXX_original.txt`
  → 유튜브 강의 전사본

* `outputs/XXX_rich_mindset.txt`
  → '부자의 사고법' 스타일로 재작성된 강의 스크립트

* `outputs/XXX_rich_mindset_ko_male.mp3`
  → 재작성 스크립트로 생성된 진중한 남성 한국어 TTS 오디오

