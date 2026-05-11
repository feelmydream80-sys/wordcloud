# 다각도 분석 시스템 — 개발 계획서

> **목적**: 단순 워드클라우드 생성기를 넘어, 인사 평가 데이터를 다양한 관점에서 분석하고 인사이트를 제공하는 통합 분석 시스템 구축
> **활용 범위**: 인사 평가뿐 아니라 고객 민원, 만족도 조사 등 텍스트 기반 피드백 데이터의 변화 추세 분석에도 적용 가능

---

## 목차

1. [Phase 0: 데이터 계층 이해](#phase-0-데이터-계층-이해)
2. [Phase 1: 다각도 워드클라우드](#phase-1-다각도-워드클라우드)
3. [Phase 2: 시계열 트렌드 분석](#phase-2-시계열-트렌드-분석)
4. [Phase 3: 키워드-감정 상관 분석](#phase-3-키워드-감정-상관-분석)
5. [Phase 4: 리더십 역량 히트맵](#phase-4-리더십-역량-히트맵)
6. [Phase 5: Anomaly 탐지](#phase-5-anomaly-탐지)
7. [Phase 6: 직원 간 Wordcloud 비교](#phase-6-직원-간-wordcloud-비교)
8. [Phase 7: HR 리포트 내보내기](#phase-7-hr-리포트-내보내기)
9. [전체 아키텍처 요약](#전체-아키텍처-요약)
10. [우선순위 및 일정](#우선순위-및-일정)

---

## Phase 0: 데이터 계층 이해

### 3계층 데이터 파일 구조

```
processed_data/batch/batch_YYYYMMDD_N/
├── imeta/                          # Layer 1: 개별 평가
│   └── eval-{emp_id}-{idx}.json    → 1개 evaluation + NLP/감정 분석 결과
├── tmeta/
│   ├── employee_E001.json          # Layer 2: 직원 통합 (per-employee)
│   │   └── consolidated_analysis   → 이 직원 ONLY 집계!
│   ├── employee_E002.json
│   └── batch_summary.json          # Layer 3: 🟢 배치 전체 (핵심)
│       └── employee_results[].metadata  → 모든 직원의 전체 메타데이터 EMBED
└── word/
    └── wordcloud_E001.png
```

### 핵심 포인트

- **`batch_summary.json` 하나로 모든 분석 가능**: 모든 직원의 `evaluations[]`가 내장되어 있어 cross-employee 집계에 추가 데이터 로드 불필요
- **`consolidated_analysis`는 per-employee**: 절대 cross-employee 데이터로 오인하지 말 것
- **Dimension 필드**: 각 evaluation의 `evaluator_position`, `evaluator_department`, `evaluation_date` — 이 필드들로 필터링/그룹핑 수행

---

## Phase 1: 다각도 워드클라우드

### 개요

기존 `regenerate_wordcloud`가 항상 모든 평가를 사용하는 것을 확장하여, 특정 관점(dimension)으로 필터링한 평가 subset만으로 워드클라우드를 생성한다.

### 분석 관점

| 관점 | 필터 조건 | 인사이트 예시 |
|------|----------|-------------|
| **직급별** | `evaluator_position` = "과장" | "과장은 '리더십'을, 사원은 '협력'을 강조 → 관리층과 실무진의 관점 차이" |
| **타부서별** | `evaluator_department` = "생산부" | "생산부는 '성실성'을, 마케팅부는 '창의성'을 강조 → 부서별 중점 가치 차이" |
| **연차별** | `evaluation_date` year = "2026" | "2025년은 '개선 필요', 2026년은 '향상' 증가 → 시간 흐름에 따른 인식 변화" |
| **종합** | 필터 없음 (전체 통합) | "전사적으로 가장 많이 언급된 키워드 → 조직 전체 강점/약점" |

### 데이터 흐름

```
batch_summary.json 로드
  → employee_results[] 순회
    → 각 employee의 evaluations[] 순회
      → dimension(e.g. evaluator_position='과장')으로 필터
        → filtered_nlp_words[] 수집
  → 모든 직원의 filtered_nlp_words 통합
    → word_frequency = Counter(filtered_nlp_words)
    → word_scores = 각 단어별 감정 점수 (필터링된 평가 기준으로 재계산)
  → WordCloudGenerator.generate_with_colors_and_options()
```

### 변경 파일

| 파일 | 변경 내용 | 규모 |
|------|---------|------|
| `src/services/wordcloud_service.py` | — `filter_evaluations_across_employees()`: 모든 employee의 evaluations[]를 dimension 기준 필터<br>— `aggregate_wordcloud_data()`: 필터링된 평가 집계 → word_freq + word_scores<br>— `generate_perspective_wordcloud()`: dimension+value로 통합 WC 1개 생성<br>— `generate_grouped_wordclouds()`: dimension의 모든 그룹값별 WC 일괄 생성 | ~250줄 |
| `src/routes/wordcloud_routes.py` | `POST /api/wordcloud/perspective` — 단일 관점 WC<br>`POST /api/wordcloud/perspective/groups` — 그룹별 일괄 WC<br>`GET /api/wordcloud/perspective/values` — 관점별 사용 가능 값 목록 | ~50줄 |
| `web/templates/wordcloud.html` | 탭 메뉴 + 그룹별 WC 그리드 + 통계 테이블 | ~300줄 |
| `web/static/js/wordcloud.js` | 관점 전환, 그룹 선택, 재생성 로직 | ~200줄 |

### UI 구성

```
[배치 선택]  [직원 선택]

[분석 관점 선택]
 [직급별] [부서별] [연차별] [종합]  ← 탭

── 직급별 뷰 ──────────────────────────
┌─ "과장" 평가 통합 WC ──────────────┐
│         [WordCloud Image]          │
│  15명, 18개 평가 | 긍정 72%        │
│  상위 단어: 역량(10), 리더십(8)...   │
└────────────────────────────────────┘

┌─ 그룹별 일괄 보기 ──────────────────┐
│ ┌──────┐ ┌──────┐ ┌──────┐       │
│ │ 사원  │ │ 대리  │ │ 과장  │       │
│ │[WC]  │ │[WC]  │ │[WC]  │       │
│ │12개  │ │8개   │ │10개  │       │
│ └──────┘ └──────┘ └──────┘       │
│ ┌──────┐ ┌──────┐                │
│ │ 차장  │ │ 부장  │                │
│ │[WC]  │ │[WC]  │                │
│ │5개   │ │3개   │                │
│ └──────┘ └──────┘                │
└────────────────────────────────────┘
```

---

## Phase 2: 시계열 트렌드 분석

### 개요

`evaluation_date`를 활용하여 시간 흐름에 따른 평가 키워드 변화와 감정 추이를 분석한다.

### 인사이트 예시

- "12월에는 '개선 필요'가 40%였는데 1월에는 '향상'이 60%로 증가 → 교육/피드백 효과?"
- "연말에는 부정 평가 비율이 증가, 연초에는 긍정 평가 증가 → 계절적 패턴"
- "특정 부서의 감정 점수가 최근 3개월간 지속 하락 → 조기 개입 필요"

### 데이터 흐름

```
batch_summary.json 로드
  → 모든 evaluation을 evaluation_date 기준으로 월/분기/연도 그룹핑
  → 각 기간별:
      - word_frequency 계산 → 기간별 대표 키워드 추출
      - 평균 감정 점수(positive/negative/neutral) 계산
      - 긍정/부정 단어 비율 계산
  → 시계열 데이터 생성: [{period, keywords, sentiment, volume}, ...]
```

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `src/services/trend_service.py` (신규) | 시계열 분석 전담 서비스: `analyze_temporal_trends()`, `extract_period_keywords()` |
| `src/routes/trend_routes.py` (신규) | `GET /api/trends/summary` — 전체 트렌드 요약<br>`GET /api/trends/by-dimension` — 특정 dimension별 트렌드<br>`GET /api/trends/keywords` — 기간별 키워드 변화 |
| `web/templates/trends.html` (신규) | 라인 차트(감정 추이), 버블 차트(키워드 변화), 바 차트(기간별 평가량) |
| `web/static/js/trends.js` (신규) | Chart.js 기반 시각화 |

### UI 구성

```
[기간 선택: 2025-12 ~ 2026-01]  [그룹: 전체/부서별/직급별]

── 감정 추이 ─────────────────────────
  ▲ 긍정율(%)
  │       ●──●
  │  ●──●     ●──●
  │     ●──●
  │                      ●──●  ← 부정율
  └──────────────────────────▶ 시간(월)
  12월    1월

── 기간별 핵심 키워드 ─────────────────
  12월: [개선(8) 부족(5) 필요(4)]  ← 부정 키워드 중심
   1월: [향상(10) 우수(7) 만족(6)]  ← 긍정 키워드 증가

── 기간별 상세 ──────────────────────
  | 기간 | 평가수 | 긍정 | 부정 | 중립 | 주요키워드 |
  |------|-------|------|------|------|-----------|
  | 12월 | 20    | 45%  | 35%  | 20%  | 개선,부족 |
  | 1월  | 30    | 65%  | 20%  | 15%  | 향상,우수 |
```

---

## Phase 3: 키워드-감정 상관 분석

### 개요

현재 wordcloud의 감정 색상(빨강/초록)에만 사용되는 `word_scores`를 독립적인 분석 기능으로 분리한다.

### 인사이트 예시

- "**'커뮤니케이션'** → 긍정 30% / 부정 70% → 이 단어는 위험 신호, HR 개입 필요"
- "**'팀워크'** → 긍정 90% / 부정 5% → 항상 긍정 맥락, 핵심 강점 키워드"
- "과장이 사용하는 '커뮤니케이션'은 긍정적이지만, 사원이 사용하면 부정적 → 직급별 인식 차이"

### 데이터 흐름

```
batch_summary.json 로드
  → 모든 evaluation에서 단어 추출 (명사/동사 기준)
  → 단어별 감정 점수 평균 계산 (기존 calculate_word_scores 로직 재사용)
  → 결과 정렬: 가장 긍정적인 단어 TOP N / 가장 부정적인 단어 TOP N
  → dimension별 추가 분류 가능: evaluator_position별, evaluator_department별
```

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `src/services/correlation_service.py` (신규) | `analyze_word_sentiment_correlation()`: 단어-감정 상관 분석<br>`get_dimension_correlation()`: dimension별 상관 분석<br>`get_top_bottom_words()`: 최고/최저 감정 단어 |
| `src/routes/correlation_routes.py` (신규) | `POST /api/correlation/analyze` — 상관 분석 실행<br>`GET /api/correlation/top-words` — 긍정/부정 Top N |
| `web/templates/correlation.html` (신규) | 단어×감정 산점도, 긍정/부정 단어 리스트, dimension별 비교 |

### UI 구성

```
── 단어-감정 상관 분석 ────────────────

[분석 대상: 전체 평가] [필터: 과장 평가]

  긍정 단어 TOP 5              부정 단어 TOP 5
  ┌─────────────────────┐   ┌─────────────────────┐
  │ 향상          +0.92 │   │ 개선          -0.78 │
  │ 팀워크        +0.88 │   │ 부족          -0.75 │
  │ 만족          +0.85 │   │ 필요          -0.65 │
  │ 우수          +0.82 │   │ 문제          -0.60 │
  │ 협력          +0.80 │   │ 개선필요      -0.55 │
  └─────────────────────┘   └─────────────────────┘

   단어 감정 분포 (산점도)
  ┌─────────────────────────────────┐
  │  긍정↑   향상●  팀워크●         │
  │          협력●   만족●          │
  │     의사소통●                    │
  │  중립─ ─ ─ ─ ─ ─ ─ ─ ─ ─     │
  │                     문제●       │
  │             개선●    부족●      │
  │  부정↓ ─ ─ ─ ─ ─ ─ ─ ─ ─     │
  └─────────────────────────────────┘
   출현빈도→ (버블 크기 = 출현 빈도)
```

---

## Phase 4: 리더십 역량 히트맵

### 개요

이미 모든 평가에 계산된 `leadership_analysis_results`를 시각화한다. 6개 역량(communication, leadership, problem_solving, teamwork, innovation, ethics)을 dimension별로 집계하여 히트맵으로 표현한다.

### 인사이트 예시

- "생산부는 communication(0.3)이 약하고, 마케팅부는 innovation(0.8)이 강함 → 부서별 교육 방향"
- "과장급은 전반적 리더십(0.7)이 높지만 대리급은 낮음(0.4) → 승격 전 교육 필요"
- "innovation 점수가 전사적으로 낮음(0.2) → 조직 문화 개선 필요"

### 데이터 흐름

```
batch_summary.json 로드
  → 모든 employee의 consolidated_analysis.leadership_consolidated.average_competencies 추출
  → dimension별 집계: 부서별 평균, 직급별 평균, 연차별 평균
  → 2차원 히트맵 데이터 생성: {row: 부서, col: 역량, value: 평균점수}
```

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `src/services/leadership_service.py` (신규) | `aggregate_leadership_scores()`: dimension별 리더십 집계<br>`get_leadership_heatmap()`: 히트맵 데이터 생성<br>`get_leadership_gaps()`: 역량별 Gap 분석 |
| `src/routes/leadership_routes.py` (신규) | `POST /api/leadership/heatmap` — 히트맵 데이터<br>`GET /api/leadership/summary` — 리더십 요약<br>`GET /api/leadership/gaps` — 역량 격차 분석 |
| `web/templates/leadership.html` (신규) | 히트맵(Chart.js/Heatmap.js), 레이더 차트, 갭 분석 테이블 |

### UI 구성

```
── 리더십 역량 히트맵 ────────────────

  [기준: 부서별] [직급별] [연차별]

         Comm  Lead  Prob  Team  Innov  Ethic
  생산부  0.3   0.5   0.6   0.7   0.2    0.4    ← 낮음(빨강)
  인사부  0.8   0.6   0.5   0.7   0.3    0.9    ← 높음(초록)
  마케팅  0.6   0.4   0.7   0.6   0.8    0.5
  재무부  0.4   0.3   0.8   0.5   0.1    0.7
  영업부  0.7   0.6   0.6   0.5   0.4    0.3

  [색상: 빨강(낮음) → 노랑(중간) → 초록(높음)]

── 역량별 갭 분석 ────────────────────
  Innovation: 전사 평균 0.20 (최하) → 교육 우선순위 1
  Communication: 생산부 0.30 (타부서 평균 0.62 대비 -0.32) → 부서 집중 교육
```

---

## Phase 5: Anomaly 탐지

### 개요

각 직원의 평가 지표(sentiment, profanity 비율, leadership score)를 동일 그룹(부서/직급)의 평균과 비교하여 이상치를 탐지한다.

### 인사이트 예시

- "U007: 같은 생산부 평균 긍정도 85%인데 U007는 45% → 집중 검토 필요 (붉은색)"
- "U011: 비속어 포함 평가 비율 66% (전사 평균 5%) → HR 즉시 개입"
- "U014: 리더십 점수가 동일 직급 평균 대비 -2σ → 리더십 코칭 필요"

### 데이터 흐름

```
batch_summary.json 로드
  → dimension별 baseline 계산: 평균, 표준편차 (부서별/직급별/전체)
  → 각 employee를 baseline과 비교:
      - sentiment z-score
      - profanity ratio z-score
      - leadership score z-score
  → z-score > 2 또는 < -2 → anomaly 플래그
  → anomaly 심각도: normal / warning / critical
```

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `src/services/anomaly_service.py` (신규) | `calculate_baseline()`: dimension별 baseline 통계<br>`detect_anomalies()`: 이상치 탐지<br>`get_anomaly_report()`: 이상치 보고서 생성 |
| `src/routes/anomaly_routes.py` (신규) | `POST /api/anomaly/detect` — 이상치 탐지 실행<br>`GET /api/anomaly/report` — 보고서 조회<br>`GET /api/anomaly/by-employee/:id` — 특정 직원 상세 |
| `web/templates/anomaly.html` (신규) | 이상치 리스트(심각도별 색상), 직원 상세 모달, dimension별 필터 |

### UI 구성

```
── Anomaly 탐지 ──────────────────────
  [기준: 전체 평균 대비] [부서 평균 대비] [직급 평균 대비]

  🟥 긴급 검토 (z > 3)
  ┌────────────────────────────────────────────┐
  │ U011  │ 긍정도 22% (전체평균 72% vs -4.2σ) │ ← 빨강
  │       │ 비속어율 66% (전체평균 5% vs +8.1σ) │
  └────────────────────────────────────────────┘

  🟨 주의 (z > 2)
  ┌────────────────────────────────────────────┐
  │ U007  │ 긍정도 45% (생산부평균 85% vs -3.1σ)│ ← 노랑
  │ U014  │ 리더십 0.15 (동기 vs -2.5σ)         │
  └────────────────────────────────────────────┘

  🟩 정상 범위 — 12명
```

---

## Phase 6: 직원 간 Wordcloud 비교

### 개요

현재는 한 번에 한 명의 직원 wordcloud만 볼 수 있어 비교가 어렵다. 2~4명을 선택하여 나란히 비교하는 뷰를 제공한다.

### 인사이트 예시

- "A팀장과 B팀장의 wordcloud를 나란히 → A는 '리더십'이 크고 B는 '커뮤니케이션'이 큼 → 리더십 스타일 차이"
- "U001 vs U002: 같은 과장 평가인데 U001은 긍정 단어, U002는 '개선' 부정 단어 → 성과 차이"

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `web/templates/wordcloud.html` | 비교 모드 버튼 + 다중 선택 체크박스 + 그리드 뷰 |
| `web/static/js/wordcloud.js` | 다중 선택 로직, 비교 뷰 전환 |

### UI 구성

```
[직원 다중 선택: U001 ☑ U002 ☑ U015 ☐ ...] [비교하기]

── Wordcloud 비교 ────────────────────
┌──────────────┐  ┌──────────────┐
│   U001       │  │   U002       │
│   [WC]       │  │   [WC]       │
│   긍정 85%   │  │   긍정 35%   │
│   평가 3개   │  │   평가 3개   │
│   Top:       │  │   Top:       │
│   역량,향상  │  │   개선,부족  │
└──────────────┘  └──────────────┘
┌──────────────┐  ┌──────────────┐
│   차이 분석   │  │              │
│ U001만 등장:  │  │ U002만 등장: │
│ 역량, 향상    │  │ 개선, 부족   │
└──────────────┘  └──────────────┘
```

---

## Phase 7: HR 리포트 내보내기

### 개요

지금까지의 모든 분석 결과를 단일 HTML/PDF 리포트로 내보내 인사팀 회의자료로 활용한다.

### 포함 내용

| 섹션 | 소스 |
|------|------|
| 배치 개요 | batch_info (총 평가 수, 직원 수, 기간) |
| 전사 종합 Wordcloud | Phase 1 결과 |
| 관점별 Wordcloud | Phase 1 — 직급별/부서별/연차별 |
| 시계열 트렌드 차트 | Phase 2 — 감정 추이 라인차트 |
| 키워드-감정 상관표 | Phase 3 — 긍정/부정 키워드 Top N |
| 리더십 히트맵 | Phase 4 — 부서×역량 히트맵 |
| Anomaly 리스트 | Phase 5 — 이상치 직원 목록 |
| 개별 직원 요약 | 각 직원: sentiment + top keywords + leadership |

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `src/services/report_service.py` (신규) | `generate_html_report()`: HTML 리포트 생성<br>`export_pdf()`: HTML→PDF 변환 (weasyprint 또는 puppeteer) |
| `src/routes/report_routes.py` (신규) | `POST /api/report/generate` — 리포트 생성<br>`GET /api/report/download/:id` — 다운로드 |
| `web/templates/report.html` | 리포트 템플릿 (프린트 최적화) |

---

## 전체 아키텍처 요약

```
Frontend (HTML + JS)                     Backend (Flask)
══════════════════════                   ══════════════════

wordcloud.html ──────── Phase 1 ────→  wordcloud_service.py
  (다각도 WC 탭 + 그리드)                  perspective_*()

trends.html ────────── Phase 2 ────→  trend_service.py (신규)
  (시계열 차트)                             analyze_temporal_trends()

correlation.html ───── Phase 3 ────→  correlation_service.py (신규)
  (산점도 + 순위표)                         analyze_word_sentiment()

leadership.html ────── Phase 4 ────→  leadership_service.py (신규)
  (히트맵 + 레이더)                         aggregate_leadership_scores()

anomaly.html ───────── Phase 5 ────→  anomaly_service.py (신규)
  (이상치 리스트)                           detect_anomalies()

wordcloud.html ─────── Phase 6 ────→  (기존 regenerate 활용)
  (다중 선택 비교)

report.html ────────── Phase 7 ────→  report_service.py (신규)
  (리포트 템플릿)                           generate_html_report()

                모두 batch_summary.json에서 데이터 로드
                            ↕
                    ┌──────────────────┐
                    │  batch_summary   │
                    │  .json           │  ← 🟢 단일 데이터 소스
                    │  (모든 평가 EMBED)│
                    └──────────────────┘
```

---

## 우선순위 및 일정

| Phase | 기능 | 우선순위 | 난이도 | 예상 기간 | 근거 |
|-------|------|---------|--------|----------|------|
| 1 | 다각도 워드클라우드 | 🔴 **최우선** | 중 | 4일 | 사용자 직접 요청, Phase 2~7의 기반 |
| 2 | 시계열 트렌드 분석 | 🔴 **최우선** | 중 | 3일 | 이미 있는 데이터, 인사이트 즉시 생성 가능 |
| 3 | 키워드-감정 상관 분석 | 🟡 **고** | 하 | 2일 | 기존 `word_scores` 로직 재사용 |
| 4 | 리더십 역량 히트맵 | 🟡 **고** | 중 | 2일 | 이미 계산된 데이터, 시각화만 추가 |
| 5 | Anomaly 탐지 | 🟢 **중** | 중 | 3일 | 통계 baseline만 있으면 됨 |
| 6 | 직원 간 WC 비교 | 🟢 **중** | 하 | 1일 | UI 로직만 추가 |
| 7 | HR 리포트 내보내기 | ⚪ **저** | 상 | 3일 | 모든 Phase 완료 후 통합 |

### 권장 진행 순서

```
Phase 1 ─→ Phase 2 ─→ Phase 3 ─→ Phase 4 ─→ Phase 5 ─→ Phase 6 ─→ Phase 7
(필수)     (병렬가능)  (병렬가능)  (순차)      (순차)      (병렬)     (통합)
```

Phase 1+2+3은 데이터 로드 로직을 공유하므로 동시 개발 가능. Phase 4는 별도 데이터(leadership scores) 사용하므로 독립 진행 가능.

---

> **비고**: 본 계획의 모든 기능은 `batch_summary.json` 단일 파일을 데이터 소스로 사용하므로, 추가 데이터 수집/적재 작업이 필요하지 않다. 모든 분석은 이미 배치 처리 단계에서 계산된 NLP/감정/리더십 결과를 재가공하여 이루어진다.
