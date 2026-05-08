# WordCloud 프로젝트 가이드

## 프로젝트 개요

이 프로젝트는 KcELECTRA 모델을 KOTE(Korean Online Texts Emotion) 데이터셋으로 파인튜닝하여 한국어 감정 분석 모델을 생성하고, 이를 기반으로 웹 인터페이스를 통해 긍정/부정 감정 분석을 제공하는 것을 목표로 합니다.

## 주요 문제 및 해결 과정

### 발생한 문제
- **에러**: `KeyError: 0` in `Dataset.from_list(data)`
- **원인**:
  1. raw.json이 dict 형태로 저장되어 있지만 `Dataset.from_list()`는 list를 기대함
  2. 38MB 크기의 JSON 파일을 한 번에 메모리에 로드하여 메모리 부족 발생
  3. 레이블 데이터 구조 불일치 (dict vs list)

### 해결 방안
1. **데이터 분할**: 50,000개 데이터를 1000개씩 50개 파일로 분할
2. **메모리 효율적 로딩**: 분할된 파일들을 순차적으로 로드하여 메모리 사용 최적화
3. **레이블 처리 수정**: 다중 rater의 감정을 결합하여 단일 레이블로 변환

## 프로젝트 구조

```
wordcloud_project/
├── main.py                 # 메인 애플리케이션 (CLI)
├── requirements.txt        # Python 의존성
├── run.bat                 # 실행 스크립트
├── configs/                # 설정 파일들
│   ├── sentiment_config.json  # 감정-감정 분류 설정
│   ├── emotion_config.json
│   ├── nlp_config.json
│   └── wordcloud_config.json
├── data_set/
│   └── kote/
│       ├── raw.json        # 원본 데이터 (38MB)
│       └── kote.py         # 데이터 처리 유틸리티
├── fine_tune/
│   ├── split_data.py       # 데이터 분할 스크립트
│   ├── fine_tune.py        # 파인튜닝 메인 스크립트
│   ├── data_001.json       # 분할된 데이터 파일들 (1000개씩)
│   ├── data_002.json
│   ├── ...
│   ├── data_050.json
│   ├── results/            # 학습 중간 결과
│   └── fine_tuned_model/   # 학습된 모델 저장 디렉토리
├── inputs/                 # 입력 파일들
│   └── sample_text.txt
├── logs/                   # 로그 파일들
├── model/                  # 사전 학습된 모델들
│   ├── KLUE RoBERTa/
│   ├── KLUE RoBERTa-large/
│   └── kote_for_easygoing_people/  # 파인튜닝된 모델
├── modules/                # 모듈들
│   ├── emotion_analysis.py
│   ├── nlp_analysis.py
│   └── wordcloud_generator.py
├── outputs/                # 출력 파일들
├── tests/                  # 테스트 파일들
├── utils/                  # 유틸리티
│   └── logger.py
├── web/                    # 웹 애플리케이션
│   ├── app.py              # Flask 앱
│   └── templates/          # HTML 템플릿들
│       ├── index.html
│       ├── settings.html
│       └── results.html
└── venu/                   # Python 가상환경
```

## 실행 방법

### 1. 데이터 분할 (최초 1회만 실행)
```bash
python wordcloud_project/fine_tune/split_data.py
```
- raw.json을 1000개씩 분할하여 data_*.json 파일들 생성

### 2. 파인튜닝 실행
```bash
python wordcloud_project/fine_tune/fine_tune.py
```
- 분할된 데이터 파일들을 로드하여 학습
- 학습 완료 후 fine_tuned_model/에 모델 저장

### 3. 메인 애플리케이션 실행 (CLI)
```bash
python wordcloud_project/main.py
```

### 4. 웹 애플리케이션 실행
```bash
cd wordcloud_project
venv\Scripts\activate
python web/app.py
```
- 브라우저에서 http://localhost:5000 접속
- 감정 분석 입력 페이지에서 텍스트를 입력하고 분석
- 설정 페이지에서 감정 분류를 사용자 정의 가능

## 기술적 세부 사항

### 데이터 구조
- **원본 데이터**: `{"id": {"text": "...", "labels": {"rater1": ["감정1", "감정2"], ...}}}`
- **처리 후 데이터**: `[{"text": "...", "labels": 0/1/2}]` (list of dicts)

### 감정 매핑
```python
emotion_names = [
    "불평/불만", "환영/호의", "감동/감탄", "지긋지긋", "고마움", "슬픔", "화남/분노",
    "존경", "기대감", "우쭐댐/무시함", "안타까움/실망", "비장함", "의심/불신",
    "뿌듯함", "편안/쾌적", "신기함/관심", "아껴주는", "부끄러움", "공포/무서움",
    "절망", "한심함", "역겨움/징그러움", "짜증", "어이없음", "없음", "패배/자기혐오",
    "귀찮음", "힘듦/지침", "즐거움/신남", "깨달음", "죄책감", "증오/혐오",
    "흐뭇함(귀여움/예쁨)", "당황/난처", "경악", "부담/안_내킴", "서러움",
    "재미없음", "불쌍함/연민", "놀람", "행복", "불안/걱정", "기쁨", "안심/신뢰"
]

emotion_to_sentiment = {
    0: 1, 1: 0, 2: 0, 3: 1, 4: 0, 5: 1, 6: 1, 7: 0, 8: 0, 9: 1,
    10: 1, 11: 0, 12: 1, 13: 0, 14: 0, 15: 2, 16: 0, 17: 1, 18: 1,
    19: 1, 20: 1, 21: 1, 22: 1, 23: 1, 24: 2, 25: 1, 26: 1, 27: 1,
    28: 0, 29: 0, 30: 1, 31: 1, 32: 0, 33: 1, 34: 1, 35: 1, 36: 1,
    37: 1, 38: 1, 39: 2, 40: 0, 41: 1, 42: 0, 43: 0
}
```

### 학습 설정
- **모델**: KcELECTRA-base
- **태스크**: Sequence Classification (3 classes: 긍정/부정/중립)
- **배치 크기**: 16
- **에폭**: 3
- **학습률**: 2e-5
- **최적화**: AdamW

### 성능 결과
- **총 학습 시간**: 약 12시간 51분
- **최종 손실**: 0.4503
- **평가 손실**: 0.6445 (최종 에폭)

## 주요 수정 사항

### split_data.py
- raw.json을 1000개씩 분할하여 메모리 효율적 처리
- 각 청크를 별도 JSON 파일로 저장

### fine_tune.py 주요 변경
1. **데이터 로딩**:
   ```python
   # 기존: json.load() 한 번에 전체 로드
   # 변경: glob으로 분할 파일들 로드 후 extend
   ```

2. **레이블 처리**:
   ```python
   def convert_labels_to_sentiment(labels_dict):
       # 다중 rater 감정 결합
       all_emotions = []
       for rater, emotions in labels_dict.items():
           for emotion in emotions:
               idx = emotion_name_to_index.get(emotion)
               if idx is not None:
                   all_emotions.append(idx)
       return emotion_to_sentiment.get(all_emotions[0], 2)
   ```

3. **데이터셋 매핑**:
   ```python
   # dict에 map 적용 불가 -> 각 split별 개별 적용
   tokenized_dataset = {}
   for split in dataset:
       tokenized_dataset[split] = dataset[split].map(preprocess_function, batched=True)
   ```

4. **하이퍼파라미터**:
   - `evaluation_strategy` → `eval_strategy` (transformers 버전 호환)

## 배운 점 및 모범 사례

### 메모리 관리
- 대용량 JSON 파일은 스트리밍 또는 분할 처리 권장
- `Dataset.from_generator()` 활용 고려

### 데이터 구조 검증
- Hugging Face Datasets의 입력 형식 철저히 확인
- dict vs list, 데이터 타입 일관성 검증

### 버전 호환성
- 라이브러리 버전에 따른 API 변경 사항 주의
- FutureWarning 적극 대응

### 코드 구조화
- 데이터 전처리와 학습 로직 분리
- 재사용 가능한 스크립트 설계

### 에러 처리
- 대용량 데이터 처리 시 메모리 모니터링
- 단계별 실행으로 문제 지점 식별

## 워드클라우드 색상 적용 방법

### 절대 금지 항목 (사용자 설득 전 AI 제안 방법)
- **감정어 계산 방법**: 각 단어를 개별적으로 감정 분석 모델에 입력하여 긍정/부정 확률을 계산하고, 이를 기반으로 점수를 할당
- **워드클라우드 색상 로직**: 단어 별 점수에 따라 색상을 적용 (긍정: 파랑, 부정: 빨강, 중립: 회색), 점수의 절대값에 따라 진하기 조절

**문제점**: 단어 단위 분석은 문맥을 고려하지 않아 부정 텍스트에서도 긍정 단어가 나올 수 있음

### 절대 추천 항목 (현재 구현된 방법)
- **감정어 계산 방법**: 각 문장에서 추출된 레이블(확률 > 0.1)의 점수를 합산하고, 문장이 부정인 경우 합 * (-1), 긍정인 경우 그대로 하여 점수를 계산. 그 점수를 문장에서 나온 단어들에 할당
- **워드클라우드 색상 로직**: 단어 별 점수에 따라 색상 결정 (양수: 파랑, 음수: 빨강, 0: 회색), 점수의 절대값에 따라 색상 진하기 조절 (0 ~ 1 범위)

**장점**: 문장 별 감정을 반영하여 단어 별로 적절한 색상 적용

## 데이터 정제 기능

프로젝트에 데이터 정제 모듈이 추가되어 사용자 번호별로 데이터를 분리할 수 있습니다.

### 사용 방법

1. **웹 인터페이스**: `/preprocess` 페이지에서 CSV 파일을 업로드
2. **데이터 미리보기**: 최상위 10행을 테이블로 표시
3. **열 선택**: 사용자 번호가 있는 열을 라디오 버튼으로 선택
4. **정제 시작**: 선택된 열을 기준으로 사용자별 데이터 분리 및 저장

### 기능 상세

- **입력**: CSV 파일 (첫 번째 행은 헤더)
- **처리**: pandas를 사용하여 사용자 ID별 그룹화
- **출력**: `processed_data/` 폴더에 `user_{id}.csv` 파일들 생성
- **원본 수정**: 처리된 행들을 원본 파일에서 삭제

### 모듈 구조

- `modules/data_preprocessing.py`: DataPreprocessing 클래스
- `web/templates/preprocess.html`: 웹 UI
- `web/app.py`: /upload_csv, /start_preprocessing 라우트

## 향후 개선 방향

1. **스트리밍 처리**: ijson 라이브러리 활용한 진정한 스트리밍
2. **데이터 검증**: 분할 전 데이터 무결성 체크
3. **학습 최적화**: GPU 활용, 배치 크기 튜닝
4. **모델 평가**: 추가 메트릭 (F1, Precision, Recall)
5. **배포 준비**: 모델 서빙 및 API 개발
6. **데이터 정제 확장**: 다양한 정제 옵션 추가 (중복 제거, 결측치 처리 등)

## 참고 자료

- [Hugging Face Transformers](https://huggingface.co/docs/transformers)
- [Hugging Face Datasets](https://huggingface.co/docs/datasets)
- [KcELECTRA 모델](https://huggingface.co/beomi/kcelectra-base)
- [KOTE 데이터셋](https://github.com/searle-j/KOTE)

---

**작성일**: 2026-01-13
**버전**: 1.0
**작성자**: AI Assistant
