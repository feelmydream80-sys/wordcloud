# 배치 처리 모듈화 계획

## 현재 상태
- batch_service.py: 639줄 (리팩토링 필요)
- 다양한 기능이 단일 파일에 혼합

## 분리 계획

### 1. 파일 파서 모듈 (src/services/file_parser.py) - ~150줄
- upload_batch_file() - CSV/Excel 업로드 및 인코딩 감지
- upload_csv() - 단순 CSV 업로드
- start_preprocessing() - 데이터 전처리 시작

### 2. 배치 관리 모듈 (src/services/batch_manager.py) - ~200줄
- get_batch_list() - 배치 목록 조회
- delete_batch() - 배치 삭제
- get_sample_metadata() - 샘플 메타데이터 조회

### 3. 배치 처리 모듈 (src/services/batch_processor.py) - ~300줄
- process_batch_metadata() - 배치 메타데이터 처리 (핵심 로직)
- 워드클라우드 생성 로직 포함

### 4. 이벤트 모듈 (src/services/batch_events.py) - ~50줄
- get_processing_events() - SSE 이벤트 스트리밍
- download_batch_results() - 결과 다운로드

### 5. batch_service.py - ~100줄
- 배치 관련 블루프린트 라우트 연결
- global state 관리

## 의존성 구조
```
batch_routes.py
    └── batch_service.py
            ├── file_parser.py
            ├── batch_manager.py
            ├── batch_processor.py
            └── batch_events.py
```

## 순서
1. file_parser.py 생성
2. batch_manager.py 생성  
3. batch_events.py 생성
4. batch_processor.py 생성 (가장 복잡하므로 마지막)
5. batch_service.py 단순화
6. 테스트 및 검증