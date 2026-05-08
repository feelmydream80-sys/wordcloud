# 웹 시스템 호출 체인 분석 문서

## 1. 시스템 개요

### 1.1 프로젝트 구조
```
wordcloud_project/
├── src/
│   ├── app.py              # Flask 앱 진입점 (web/app.py와 중복)
│   ├── config/settings.py # 설정 관리
│   ├── routes/             # API 엔드포인트
│   │   ├── ui_routes.py
│   │   ├── metadata_routes.py
│   │   ├── batch_routes.py
│   │   ├── wordcloud_routes.py
│   │   └── api_routes.py
│   ├── services/           # 비즈니스 로직
│   │   ├── metadata_service.py
│   │   ├── batch_service.py
│   │   └── wordcloud_service.py
│   ├── models/             # 데이터 모델
│   │   └── metadata_manager.py
│   └── modules/            # 분석 모듈
│       ├── metadata_analysis.py
│       ├── nlp_analysis.py
│       ├── emotion_analysis.py
│       ├── profanity_filter.py
│       ├── wordcloud_generator.py
│       └── ...
└── web/
    └── app.py              # 실제 사용 중인 Flask 앱
```

### 1.2 진입점 분석

| 파일 | 상태 | 설명 |
|------|------|------|
| `web/app.py` | ✅ 사용 중 | template: `web/templates/`, static: `web/static/` |
| `src/app.py` | ⚠️ 미사용 | template: `web/templates/`, static: `web/static/` (중복) |

---

## 2. 호출 체인 분석

### 2.1 배치 처리流程 (가장 복잡한流程)

```
HTTP Request
    ↓
web/app.py → Flask App
    ↓
Routes (5개 Blueprint)
    ↓
    ├─ ui_routes.py      → /
    ├─ metadata_routes.py → /api/metadata/*
    ├─ batch_routes.py   → /api/batch/*
    ├─ wordcloud_routes.py → /api/wordcloud/*
    └─ api_routes.py     → /api/*
    ↓
Services Layer
    ↓
    ├─ metadata_service.py
    │   └─ MetadataManager (src/models/metadata_manager.py)
    │   └─ calculate_consolidated_analysis (src/modules/metadata_analysis.py)
    │
    ├─ batch_service.py
    │   └─ MetadataManager (src/models/metadata_manager.py)
    │   └─ WordCloudGenerator (src/modules/wordcloud_generator.py)
    │   └─ preprocess_data (src/modules/data_preprocessing.py)
    │
    └─ wordcloud_service.py
        └─ WordCloudGenerator
    ↓
Modules Layer (분석 모듈)
    ├─ nlp_analysis.py      (Kiwi, Okt 형태소 분석)
    ├─ emotion_analysis.py (감정 분석)
    ├─ profanity_filter.py (욕설 필터)
    ├─ sarcasm_analysis.py (비꼬임 분석)
    ├─ leadership_analysis.py (리더십 분석)
    └─ wordcloud_generator.py (워드클라우드 생성)
```

### 2.2 메타데이터 관리 호출 분석

**현재 사용 중인 모듈 경로:**

| 서비스 | import 경로 | 실제 위치 |
|--------|-------------|-----------|
| MetadataManager | `src.models.metadata_manager` | `src/models/metadata_manager.py` ✓ |
| calculate_consolidated_analysis | `src.modules.metadata_analysis` | `src/modules/metadata_analysis.py` ✓ |

**기존 (deprecated) 모듈:**

| 모듈 | 상태 | 대체 경로 |
|------|------|-----------|
| `modules/metadata_manager.py` | deprecated | `src/models/metadata_manager.py` |
| `modules/metadata_analysis.py` | deprecated | `src/modules/metadata_analysis.py` |

---

## 3. 데이터 흐름

### 3.1 배치 처리 시퀀스

1. **파일 업로드** → `batch_service.upload_batch_file()`
   - CSV/Excel 파싱
   - 인코딩 자동 감지 (UTF-8, CP949, EUC-KR 등)

2. **데이터 그룹화** → `batch_service.process_batch_metadata()`
   - employee_id별 평가 데이터 그룹화

3. **메타데이터 생성** → `MetadataManager.create_employee_metadata()`
   - 각 평가에 NLP/감정/욕설/리더십 분석 수행
   - 통합 분석 결과 계산 (`calculate_consolidated_analysis`)

4. **워드클라우드 생성** → `WordCloudGenerator`
   - 감정 기반 색상 적용

5. **저장** → `MetadataManager.save_employee_metadata()`
   - JSON 파일로 저장 (`batch/batch_YYYYMMDD_X/tmeta/`)

### 3.2 메타데이터 저장 위치

| 구분 | 경로 |
|------|------|
| 배치 | `processed_data/batch/batch_YYYYMMDD_X/tmeta/employee_{id}.json` |
| 단일 | `processed_data/YYYYMM/single/employee_{id}.json` |

---

## 4. 발견된 문제점

### 4.1 중복 파일
- `web/app.py`와 `src/app.py` - 둘 다 같은 blueprint 사용
- 설정 중복: `template_folder`, `static_folder` 경로가 동일

### 4.2 불필요 데이터
- `modules/` 디렉토리 - deprecated 파일들 (metadata_manager.py, metadata_analysis.py 등)
- `check files/` 디렉토리 - 디버그/테스트 스크립트들
- `doc/` 디렉토리 내 과거 문서들

### 4.3 버전 불일치
- 메타데이터 버전 혼재 (v1.2.0-1to1, v2.1.0)
- 기존 문서와 실제 구현 간 필드 불일치

---

## 5. 리팩토링 계획

### 5.1 phase 1: 불필요 데이터 정리
- [ ] deprecated 모듈 제거 (modules/metadata_manager.py, modules/metadata_analysis.py)
- [ ] check files/ 디렉토리 정리
- [ ] 중복 app.py 제거 (web/app.py만 사용)

### 5.2 phase 2: 모듈 통합
- [ ] MetadataManager 단일化
- [ ] 메타데이터 스키마 표준화

### 5.3 phase 3: 데이터 무결성
- [ ] 버전 관리 체계 수립
- [ ] 해시 기반 무결성 검증 강화

---

## 6. 다음 단계

1. 사용자에게 분석 결과 검토 요청
2. phase 1 정리 작업 실행 여부 확인
3. 리팩토링 진행

---

**문서 작성일**: 2026-04-09
**버전**: v2.0.0