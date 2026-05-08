# WordCloud 프로젝트 모듈화 오류 분석 리포트

## 작성일시: 2026-03-24 15:48
## 프로젝트 상태: 모듈화 작업 진행 중

---

## 1. 발생한 문제 개요

### 문제 1: ModuleNotFoundError - src.modules 모듈을 찾을 수 없음
- **발생 시점**: `src/app.py` 실행 시
- **에러 메시지**: `ModuleNotFoundError: No module named 'src.modules'`
- **원인**: src 폴더 내에 modules 폴더가 없었음
- **해결 과정**: wordcloud_project/modules 폴더의 파일을 src/modules로 복사

### 문제 2: TemplateNotFound - index.html을 찾을 수 없음
- **발생 시점**: 브라우저에서 http://127.0.0.1:5001 접근 시
- **에러 메시지**: `jinja2.exceptions.TemplateNotFound: index.html`
- **원인**: Flask 앱의 템플릿 경로 설정 오류
- **현재 상태**: 해결 중

---

## 2. 모듈화 작업 과정 분석

### 2.1 진행된 작업

1. **핵심 모듈 구현 (Phase 1)**:
   - metadata_analysis.py: 통합 분석 함수 구현
   - metadata_manager.py: 메타데이터 관리 클래스 구현
   - 단위 테스트 작성 및 실행

2. **Flask 앱 모듈화 (Phase 4)**:
   - src/config/settings.py: 전역 설정 관리
   - src/routes/: Flask Blueprints 라우터 구현
     - ui_routes.py: UI 라우팅
     - metadata_routes.py: 메타데이터 관리
     - batch_routes.py: 배치 처리
     - wordcloud_routes.py: 워드클라우드 생성
     - api_routes.py: API 엔드포인트
   - src/services/: 비즈니스 로직 서비스
   - src/models/: 데이터 모델
   - src/modules/: 기능 모듈

3. **src/app.py**: Flask 앱 인스턴스 생성 및 설정

### 2.2 문제 발생 원인

#### 문제 1: ModuleNotFoundError
- **작업 과정**: src 폴더 구조를 생성할 때 modules 폴더를 빠뜨림
- **오류 원인**: src/services/metadata_service.py가 `src.modules.metadata_analysis`를 import 하려고 했으나, src/modules 폴더가 존재하지 않음
- **영향 범위**: Flask 앱 실행 실패

#### 문제 2: TemplateNotFound
- **작업 과정**: Flask 앱을 생성할 때 템플릿 경로를 명시적으로 설정하지 않음
- **오류 원인**: Flask가 기본적으로 app.py가 위치한 폴더의 templates 폴더를 찾지만, src/app.py의 경우 templates 폴더가 상대적으로 다른 위치에 있음
- **영향 범위**: 홈 페이지 접근 불가

---

## 3. 문제 해결 계획

### 문제 2 해결 (TemplateNotFound)

#### 방법 1: 템플릿 경로 설정
```python
# src/app.py
def create_app():
    app = Flask(__name__, 
                template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '../web/templates')))
    # ...
```

#### 방법 2: templates 폴더 복사
src 폴더 내에 templates 폴더를 생성하고 web/templates의 내용을 복사

---

## 4. 체크리스트 업데이트 제안

### 기존 체크리스트 문제점
현재 체크리스트는 다음과 같은 문제가 있음:
1. 세부 작업이 구체적이지 않음
2. 파일 위치나 경로 설정에 대한 검증 단계가 부족
3. 오류 발생 시 대응 단계가 없음

### 개선된 체크리스트

#### Phase 4: Flask 라우터 모듈화 작업 (수정)
- [x] ui_routes.py 생성
- [x] metadata_routes.py 생성
- [x] batch_routes.py 생성
- [x] wordcloud_routes.py 생성
- [x] api_routes.py 생성
- [ ] app.py 리팩토링 (실제 파일 변경 필요)
- [ ] src/modules 폴더 생성 및 파일 복사 (필요)
- [ ] 모듈 import 경로 수정 (필요)
- [ ] Flask 템플릿 경로 설정 (필요)
- [ ] Flask 앱 실행 테스트

#### Phase 5: 프로젝트 구조 정리
- [ ] 테스트 파일 카테고리별 폴더 생성
- [ ] 폴더 구조 확인 (Windows dir 명령)
- [ ] 테스트 파일 이동 (최종 실행)
- [ ] import 경로 수정
- [ ] 테스트 실행 확인
- [ ] README.md 생성
- [ ] wordcloud_project 폴더 내 분류 기준 설정
- [ ] 소스/데이터/문서 등 폴더 생성
- [ ] wordcloud_project 폴더 파일 이동
- [ ] root 폴더 파일 분류
- [ ] root 폴더 파일 이동
- [ ] wordcloud_project 폴더 내 파일 분류 재실행
- [ ] 폴더 구조 최종 확인

---

## 5. 향후 개선 방안

### 5.1 모듈화 전략 개선
1. **계층 구조 명확화**: 각 layer의 역할과 책임을 더 명확히 정의
2. **경로 관리 표준화**: 모든 import 경로를 상대경로 대신 절대경로로 관리
3. **설정 관리 개선**: 설정 파일을 한 곳에서 관리하고 환경변수로 구분

### 5.2 테스트 전략
1. **단위 테스트 강화**: 각 모듈별로 독립적인 테스트 작성
2. **통합 테스트**: 모듈 간 연동 테스트
3. **자동화**: CI/CD를 통해 테스트 자동화

### 5.3 문서화
1. **API 문서**: 각 서비스와 라우터의 API 문서 작성
2. **개발 가이드**: 프로젝트 구조와 사용 방법 문서화
3. **오류 처리**: 자주 발생하는 오류와 해결 방법 문서화

---

## 6. 결론

현재 모듈화 작업은 기본 구조는 잡혔으나, 세부적인 경로 설정과 구성 문제로 인해 오류가 발생하고 있습니다. 특히:

1. **src/modules 폴더 누락**: 기존 modules 폴더를 src 폴더 내로 복사해야 함
2. **템플릿 경로 설정**: Flask 앱이 템플릿 파일을 찾을 수 있도록 경로를 설정해야 함

이러한 문제를 해결한 후에는 전체 시스템의 기능 테스트를 통해 안정성을 확인해야 합니다.