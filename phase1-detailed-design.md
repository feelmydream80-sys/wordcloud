# Phase 1 상세 개발 설계 — 다각도 워드클라우드

> **기반 데이터**: `batch_summary.json` (모든 직원 메타데이터 embed)
> **목표**: 직급별/부서별/연차별/종합 관점에서 워드클라우드 생성
> **우선순위**: 🔴 최우선 (Phase 2~7의 기반)

---

## 목차

1. [데이터 접근 계층](#1-데이터-접근-계층)
2. [서비스 함수 설계](#2-서비스-함수-설계)
3. [API 엔드포인트](#3-api-엔드포인트)
4. [데이터 흐름도](#4-데이터-흐름도)
5. [UI 설계](#5-ui-설계)
6. [변경 파일 목록](#6-변경-파일-목록)
7. [엣지 케이스](#7-엣지-케이스)

---

## 1. 데이터 접근 계층

### 1.1 batch_summary.json 데이터 경로

```python
# 배치 경로 예시:
# D:\dev\wordcloud\wordcloud_project\processed_data\batch\batch_20260508_10

# 로드 방식
summary_path = os.path.join(batch_path, "tmeta", "batch_summary.json")
with open(summary_path, 'r', encoding='utf-8') as f:
    batch_summary = json.load(f)
```

### 1.2 핵심 데이터 접근 경로

```
batch_summary
└── employee_results[]                          ← 모든 직원
    └── metadata                                ← 해당 직원 전체 데이터
        ├── target_employee_id: "U001"
        ├── target_employee_department: "생산부"
        ├── target_employee_position: "사원"
        ├── total_evaluations: 3
        ├── evaluations[]                       ← 이 직원의 모든 평가
        │   └── [0]:
        │       ├── evaluation_document: "업무 역량이..."
        │       ├── evaluator_position: "과장"          ← 🎯 dimension 필드
        │       ├── evaluator_department: "인사부"       ← 🎯 dimension 필드
        │       ├── evaluation_date: "2026-01-21"        ← 🎯 dimension 필드
        │       ├── nlp_analysis_results
        │       │   └── analysis
        │       │       ├── meaningful_words: ["역량", "향상", ...]
        │       │       └── meaningful_words_with_pos: [["역량","Noun"], ["향상","Noun"], ...]
        │       └── emotion_analysis_results
        │           └── analysis
        │               └── base_result
        │                   └── mapped
        │                       └── sentiment_scores
        │                           ├── positive: 0.9658
        │                           ├── negative: 0.0066
        │                           └── neutral: 0.0275
        └── consolidated_analysis
            └── evaluator_analysis
                ├── department_distribution: {"생산부": 1, "인사부": 1, ...}
                └── position_distribution: {"사원": 1, "과장": 2, ...}
```

### 1.3 신규 유틸리티: `load_batch_summary()`

```python
# src/services/wordcloud_service.py 에 추가

def load_batch_summary(batch_path):
    """
    batch_summary.json을 직접 로드.
    
    Args:
        batch_path: 배치 디렉토리 전체 경로
                   (예: "D:/.../processed_data/batch/batch_20260508_10")
    
    Returns:
        dict: batch_summary 전체 (employee_results[].metadata 포함)
        None: 파일 없음
    
    Notes:
        - get_batch_metadata()는 개별 employee 파일을 로드하지만,
          이 함수는 batch_summary.json을 직접 로드하여 더 빠름
        - batch_summary.json에는 모든 employee의 metadata가 embed되어 있음
    """
    summary_path = os.path.join(batch_path, "tmeta", "batch_summary.json")
    if not os.path.exists(summary_path):
        print(f"batch_summary not found: {summary_path}")
        return None
    with open(summary_path, 'r', encoding='utf-8') as f:
        return json.load(f)
```

---

## 2. 서비스 함수 설계

### 2.1 `filter_evaluations_across_employees()`

```python
def filter_evaluations_across_employees(employee_results, dimension, value):
    """
    모든 직원의 evaluations[]를 dimension 기준으로 필터링.
    
    Args:
        employee_results: batch_summary['employee_results'] (list)
        dimension: 'evaluator_position' | 'evaluator_department' | 'year' | 'all'
        value: 필터 값
               - dimension='evaluator_position' → "과장"
               - dimension='evaluator_department' → "생산부"  
               - dimension='year' → "2026"
               - dimension='all' → None (필터 없음)
    
    Returns:
        list of dict: [{evaluation, employee_id, employee_dept, employee_pos}, ...]
                      각 항목은 원본 evaluation dict + 소속 직원 정보 포함
    
    Notes:
        - dimension='all'이면 모든 평가 반환 (value 무시)
        - value=None 또는 value=''이면 빈 리스트 반환
        - dimension='year'면 evaluation_date에서 연도 4자리 추출하여 비교
    """
    filtered = []
    for er in employee_results:
        meta = er.get('metadata', {})
        emp_id = meta.get('target_employee_id')
        emp_dept = meta.get('target_employee_department')
        emp_pos = meta.get('target_employee_position')
        
        for ev in meta.get('evaluations', []):
            if dimension == 'all':
                filtered.append({
                    'evaluation': ev,
                    'employee_id': emp_id,
                    'employee_department': emp_dept,
                    'employee_position': emp_pos
                })
            elif dimension == 'year':
                date_str = ev.get('evaluation_date', '')
                if len(date_str) >= 4 and date_str[:4] == str(value):
                    filtered.append({...})
            else:
                ev_value = ev.get(dimension)
                if ev_value == value:
                    filtered.append({...})
    
    return filtered
```

### 2.2 `extract_words_from_evaluations()`

```python
def extract_words_from_evaluations(filtered_evaluations, wordcloud_pos, remove_profanity=False):
    """
    필터링된 평가 리스트에서 단어 추출 및 빈도 계산.
    
    Args:
        filtered_evaluations: filter_evaluations_across_employees()의 반환값
        wordcloud_pos: 형태소 선택 리스트 (예: ['Noun', 'Verb'])
        remove_profanity: 비속어 제거 여부
    
    Returns:
        dict: {
            'word_frequency': {"역량": 5, "향상": 3, ...},
            'total_words': 42,
            'total_evaluations': 18,
            'total_employees': 10,
            'evaluation_ids': ['eval-...', ...]
        }
    
    Notes:
        - meaningful_words_with_pos에서 wordcloud_pos에 해당하는 단어만 추출
        - meaningful_words_with_pos가 없으면 meaningful_words 사용 (POS 필터링 불가)
        - remove_profanity=True면 profanity_analysis_results.detected_profanity 참조
    """
```

### 2.3 `calculate_word_scores_from_evaluations()`

```python
def calculate_word_scores_from_evaluations(filtered_evaluations, word_frequency):
    """
    필터링된 평가 subset 기준으로 단어별 감정 점수 재계산.
    
    Args:
        filtered_evaluations: filter_evaluations_across_employees()의 반환값
        word_frequency: extract_words_from_evaluations()의 word_frequency 결과
    
    Returns:
        dict: {word: score, ...}
              score > 0 = 긍정, score < 0 = 부정, score = 0 = 중립
    
    Notes:
        - 기존 calculate_word_scores()와 동일한 알고리즘
        - 단, 모든 employee가 아닌 filtered_evaluations만 대상으로 계산
        - positive_score - negative_score 차이에 2.5x 증폭
    """
```

### 2.4 `get_available_perspective_values()`

```python
def get_available_perspective_values(employee_results, dimension):
    """
    특정 dimension에서 사용 가능한 값 목록과 각 값별 평가 수 반환.
    
    Args:
        employee_results: batch_summary['employee_results']
        dimension: 'evaluator_position' | 'evaluator_department' | 'year'
    
    Returns:
        list of dict: [
            {'value': '과장', 'count': 12, 'label': '과장'},
            {'value': '사원', 'count': 10, 'label': '사원'},
            ...
        ]
        count = 해당 값으로 필터링되는 평가의 총 개수
    
    Notes:
        - 값은 출현 빈도(count) 내림차순 정렬
        - dimension='year'인 경우 evaluation_date에서 연도 추출
        - count=0인 값은 제외
    """
```

### 2.5 `generate_perspective_wordcloud()`

```python
def generate_perspective_wordcloud(data):
    """
    다각도 워드클라우드 생성 (메인 함수).
    
    Args:
        data (dict): {
            'batch_path': '.../batch_20260508_10',      # 필수
            'perspective_type': 'evaluator_position',    # 필수
            'perspective_value': '과장',                  # 필수 (all이면 None)
            'employee_id': 'U001',                       # 선택: 특정 직원만
            'wordcloud_pos': ['Noun'],                   # 선택: 기본 ['Noun']
            'background_color': 'white',                 # 선택: 기본 'white'
            'apply_emotion_colors': True,                # 선택: 기본 True
            'remove_profanity': False,                   # 선택: 기본 False
            'width': 800, 'height': 600,                 # 선택: 기본 800x600
            'max_words': 100                              # 선택: 기본 100
        }
    
    Returns:
        dict: {
            'success': True/False,
            'wordcloud_url': '/api/wordcloud/...',       # 성공 시
            'wordcloud_info': {
                'word_frequency': {...},
                'word_scores': {...},
                'total_words': 42,
                'morphology_types': ['Noun'],
                'generation_timestamp': '...',
                'perspective': {
                    'type': 'evaluator_position',
                    'value': '과장'
                },
                'stats': {
                    'total_evaluations': 18,
                    'total_employees': 10,
                    'average_sentiment': {...}
                }
            },
            'error': '...'                               # 실패 시
        }
    
    Behavior:
        1. batch_summary.json 로드
        2. employee_results[] 추출
        3. employee_id가 지정된 경우 → 해당 employee만 대상
           employee_id가 없는 경우 → 모든 employee 대상
        4. filter_evaluations_across_employees()로 평가 필터링
        5. filtered_evaluations가 비어있으면 → error
        6. extract_words_from_evaluations()로 단어 추출
        7. calculate_word_scores_from_evaluations()로 감정 점수
        8. WordCloudGenerator.generate_with_colors_and_options()로 이미지 생성
        9. 결과 URL + 통계 반환
    """
```

### 2.6 `generate_grouped_wordclouds()`

```python
def generate_grouped_wordclouds(data):
    """
    특정 dimension의 모든 그룹값에 대해 워드클라우드 일괄 생성.
    
    Args:
        data (dict): {
            'batch_path': '...',                         # 필수
            'perspective_type': 'evaluator_position',     # 필수
            'wordcloud_pos': ['Noun'],
            'background_color': 'white',
            'apply_emotion_colors': True,
            'remove_profanity': False,
            'width': 800, 'height': 600,
            'max_words': 100
        }
    
    Returns:
        dict: {
            'success': True,
            'groups': {
                '사원': {
                    'wordcloud_url': '...',
                    'evaluation_count': 12,
                    'employee_count': 8,
                    'wordcloud_info': {...}
                },
                '과장': {
                    'wordcloud_url': '...',
                    'evaluation_count': 10,
                    'employee_count': 7,
                    'wordcloud_info': {...}
                },
                '대리': {
                    'wordcloud_url': null,
                    'evaluation_count': 3,
                    'employee_count': 2,
                    'warning': '평가 수가 5개 미만입니다. (3개)',
                    'wordcloud_info': null
                },
                ...  (count=0인 그룹은 제외)
            }
        }
    
    Behavior:
        1. get_available_perspective_values()로 그룹값 목록 조회
        2. 각 그룹값에 대해 generate_perspective_wordcloud() 호출
        3. ThreadPoolExecutor로 병렬 생성 (선택)
        4. 평가 수 < 5개인 그룹은 워드클라우드 생성 skip + warning
    """
```

---

## 3. API 엔드포인트

### 3.1 신규 라우트: `perspective_routes.py`

```python
# src/routes/perspective_routes.py (신규 생성)

from flask import Blueprint, request, jsonify
perspective_bp = Blueprint('perspective', __name__, url_prefix='/api/perspective')
```

| Endpoint | Method | Request Body | Response | Description |
|----------|--------|-------------|----------|-------------|
| `/api/perspective/values` | POST | `{batch_path, dimension}` | `{values: [{value, count, label}, ...]}` | 특정 dimension의 사용 가능한 값 조회 |
| `/api/perspective/wordcloud` | POST | Phase 1 전체 파라미터 | `{success, wordcloud_url, wordcloud_info}` | 단일 관점 워드클라우드 생성 |
| `/api/perspective/groups` | POST | Phase 1 (employee_id 제외) | `{success, groups: {...}}` | 전체 그룹 일괄 생성 |

#### POST `/api/perspective/values`

```json
// Request
{
    "batch_path": "processed_data/batch/batch_20260508_10",
    "dimension": "evaluator_position"
}

// Response (200)
{
    "success": true,
    "values": [
        {"value": "사원", "count": 11, "label": "사원"},
        {"value": "과장", "count": 12, "label": "과장"},
        {"value": "대리", "count": 14, "label": "대리"},
        {"value": "차장", "count": 7, "label": "차장"},
        {"value": "부장", "count": 6, "label": "부장"}
    ],
    "batch_info": {
        "total_evaluations": 50,
        "unique_employees": 15
    }
}

// Error Response
{"success": false, "error": "존재하지 않는 배치 경로입니다."}
```

#### POST `/api/perspective/wordcloud`

```json
// Request — 직급='과장' 기준 전체 통합 WC
{
    "batch_path": "processed_data/batch/batch_20260508_10",
    "perspective_type": "evaluator_position",
    "perspective_value": "과장",
    "employee_id": null,
    "wordcloud_pos": ["Noun"],
    "background_color": "white",
    "apply_emotion_colors": true,
    "remove_profanity": false,
    "width": 800,
    "height": 600,
    "max_words": 100
}

// Request — 직급='과장' 기준, U001 개인 WC
{
    "batch_path": "processed_data/batch/batch_20260508_10",
    "perspective_type": "evaluator_position",
    "perspective_value": "과장",
    "employee_id": "U001",
    ...
}

// Response (200)
{
    "success": true,
    "wordcloud_url": "/api/wordcloud/outputs/persp_eval-pos_과장_20260511_143022.png",
    "wordcloud_info": {
        "word_frequency": {"역량": 5, "팀워크": 3, ...},
        "word_scores": {"역량": 0.85, "팀워크": 0.72, ...},
        "total_words": 28,
        "morphology_types": ["Noun"],
        "background_color": "white",
        "generation_timestamp": "2026-05-11T14:30:22Z",
        "perspective": {
            "type": "evaluator_position",
            "value": "과장"
        },
        "stats": {
            "total_evaluations": 12,
            "total_employees": 8,
            "average_sentiment": {
                "positive": 0.72,
                "negative": 0.18,
                "neutral": 0.10
            }
        }
    }
}

// Error Response (400)
{"success": false, "error": "필터링된 평가가 없습니다. (perspective_value='대리')"}

// Error Response (400)
{"success": false, "error": "필터링된 평가가 충분하지 않습니다. 최소 3개 필요 (현재 2개)"}
```

#### POST `/api/perspective/groups`

```json
// Request
{
    "batch_path": "processed_data/batch/batch_20260508_10",
    "perspective_type": "evaluator_position",
    "wordcloud_pos": ["Noun"],
    "background_color": "white",
    "apply_emotion_colors": true,
    "remove_profanity": false,
    "width": 800,
    "height": 600,
    "max_words": 100
}

// Response (200) — partial success 허용
{
    "success": true,
    "groups": {
        "사원": {
            "wordcloud_url": "/api/wordcloud/outputs/persp_eval-pos_사원_20260511_143022.png",
            "evaluation_count": 11,
            "employee_count": 7,
            "wordcloud_info": {...}
        },
        "과장": {
            "wordcloud_url": "/api/wordcloud/outputs/persp_eval-pos_과장_20260511_143025.png",
            "evaluation_count": 12,
            "employee_count": 8,
            "wordcloud_info": {...}
        },
        "대리": {
            "wordcloud_url": null,
            "evaluation_count": 3,
            "employee_count": 2,
            "warning": "평가 수 부족 (3개, 최소 5개 필요)"
        }
    }
}
```

### 3.2 wordcloud_routes.py 변경

```python
# 기존 파일에 perspective 라우트 추가
# 또는 별도 perspective_routes.py 생성

# app.py에 블루프린트 등록 필요:
# from src.routes.perspective_routes import perspective_bp
# app.register_blueprint(perspective_bp)
```

---

## 4. 데이터 흐름도

### 4.1 전체 통합 WC (직급='과장')

```
Client                              Server
  │                                   │
  │ POST /api/perspective/wordcloud   │
  │ {perspective_type: "position",    │
  │  perspective_value: "과장",       │
  │  employee_id: null}               │
  │─────────────────────────────────>│
  │                                   │
  │                              load_batch_summary(batch_path)
  │                                   │
  │                              ┌────┴─────────────────────┐
  │                              │ batch_summary.json       │
  │                              │ employee_results[].metadata│
  │                              │   └─ U001.evaluations[]  │
  │                              │   └─ U002.evaluations[]  │
  │                              │   └─ ... (15명)          │
  │                              └────┬─────────────────────┘
  │                                   │
  │                              filter_evaluations_across_employees(
  │                                employee_results,
  │                                'evaluator_position', '과장'
  │                              )
  │                                   │
  │                              ┌────┴─────────────────────┐
  │                              │ Result: 12 evaluations   │
  │                              │ from 8 employees          │
  │                              │ (모든 과장 평가 통합)     │
  │                              └────┬─────────────────────┘
  │                                   │
  │                              extract_words_from_evaluations()
  │                                   │ → word_frequency: {역량:5,...}
  │                                   │
  │                              calculate_word_scores_from_evaluations()
  │                                   │ → word_scores: {역량:0.85,...}
  │                                   │
  │                              WordCloudGenerator.generate_with_colors_and_options()
  │                                   │ → PNG 저장
  │                                   │
  │  {success, wordcloud_url,         │
  │   wordcloud_info: {stats: {       │
  │     total_evaluations: 12,        │
  │     total_employees: 8,           │
  │     average_sentiment: {0.72,...} │
  │   }}}                             │
  │<─────────────────────────────────│
```

### 4.2 개인+관점 WC (직급='과장', 직원='U001')

```
위와 동일하나 filter_evaluations_across_employees() 전에
employee_id='U001'에 해당하는 metadata만 추출 → 그 안에서만 필터링

→ 기존 regenerate_wordcloud와 동일한 데이터 범위이지만
  dimension 필터가 추가됨
```

### 4.3 이미지 파일명 규칙

```
outputs/persp_{dimension}_{value}_{timestamp}.png
outputs/persp_eval-pos_과장_20260511_143022.png
outputs/persp_eval-dept_생산부_20260511_143025.png
outputs/persp_year_2026_20260511_143030.png
outputs/persp_all_ALL_20260511_143035.png

employee_id가 지정된 경우:
outputs/persp_U001_eval-pos_과장_20260511_143022.png
```

---

## 5. UI 설계

### 5.1 페이지 구조

기존 `wordcloud.html`에 탭 영역과 그리드 뷰를 추가 (신규 페이지 또는 기존 확장).

**우선 기존 `wordcloud.html` 확장 방식 사용** — 새 페이지를 추가하면 배치/직원 선택 UI를 중복 개발해야 함.

### 5.2 추가될 HTML 영역

```html
<!-- wordcloud.html 내 Perspective 영역 (wordcloudOptions 아래) -->

<!-- ===== 관점 선택 탭 ===== -->
<div id="perspectiveSection" class="wordcloud-options" style="display:none;">
  <h3>🔍 분석 관점</h3>
  
  <!-- 탭 메뉴 -->
  <div class="perspective-tabs">
    <button class="perspective-tab active" data-dimension="evaluator_position">
      📋 직급별
    </button>
    <button class="perspective-tab" data-dimension="evaluator_department">
      🏢 부서별  
    </button>
    <button class="perspective-tab" data-dimension="year">
      📅 연차별
    </button>
    <button class="perspective-tab" data-dimension="all">
      📊 종합
    </button>
  </div>

  <!-- 관점 값 선택 드롭다운 (종합 탭에서는 숨김) -->
  <div id="perspectiveValueSelector">
    <label>세부 선택:</label>
    <select id="perspectiveValue"></select>
    <button id="applyPerspectiveBtn" class="btn btn-primary">워드클라우드 생성</button>
    <button id="generateAllGroupsBtn" class="btn btn-secondary">모든 그룹 일괄 생성</button>
  </div>
</div>

<!-- ===== 개별 관점 WC 결과 ===== -->
<div id="perspectiveWordcloudContainer" style="display:none;">
  <h3 id="perspectiveTitle">과장 평가 — 통합 워드클라우드</h3>
  <div class="perspective-stats">
    <span class="stat-badge">📊 12개 평가</span>
    <span class="stat-badge">👥 8명 대상</span>
    <span class="stat-badge positive">😊 긍정 72%</span>
    <span class="stat-badge negative">😠 부정 18%</span>
  </div>
  <img id="perspectiveWordcloudImage" src="" style="max-width:100%">
  <div id="perspectiveWordcloudInfo"></div>
</div>

<!-- ===== 그룹별 일괄 WC 그리드 ===== -->
<div id="groupGridContainer" style="display:none;">
  <h3>그룹별 워드클라우드</h3>
  <div id="groupGrid" class="group-grid">
    <!-- JS로 동적 생성 -->
    <!-- 
    <div class="group-card">
      <h4>과장 (12개 평가)</h4>
      <img src="..." class="group-wc-thumb">
      <div class="group-stats">긍정 72%</div>
    </div>
    -->
  </div>
</div>
```

### 5.3 JS 추가 로직

```javascript
// wordcloud.html 내 기존 JS에 추가

// ===== Perspective 상태 =====
let currentDimension = 'evaluator_position';
let availableValues = [];
let selectedBatchPath = null;

// ===== 탭 전환 =====
document.querySelectorAll('.perspective-tab').forEach(tab => {
  tab.addEventListener('click', function() {
    document.querySelectorAll('.perspective-tab').forEach(t => t.classList.remove('active'));
    this.classList.add('active');
    currentDimension = this.dataset.dimension;
    
    if (currentDimension === 'all') {
      document.getElementById('perspectiveValueSelector').style.display = 'none';
      loadPerspectiveValues(); // 'all'에 대한 값 로드
    } else {
      document.getElementById('perspectiveValueSelector').style.display = 'block';
      loadPerspectiveValues(); // 선택된 dimension의 값 목록 로드
    }
  });
});

// ===== 관점 값 목록 로드 =====
async function loadPerspectiveValues() {
  if (!selectedBatchPath) return;
  
  const response = await fetch('/api/perspective/values', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      batch_path: selectedBatchPath,
      dimension: currentDimension
    })
  });
  const result = await response.json();
  
  if (result.success) {
    availableValues = result.values;
    const select = document.getElementById('perspectiveValue');
    select.innerHTML = '';
    result.values.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v.value;
      opt.textContent = `${v.label} (${v.count}개 평가)`;
      select.appendChild(opt);
    });
  }
}

// ===== 단일 관점 WC 생성 =====  
async function generatePerspectiveWordcloud() {
  const perspectiveValue = currentDimension === 'all' ? null 
    : document.getElementById('perspectiveValue').value;
  
  const selectedPos = collectSelectedPos(); // 기존 함수 재사용
  const options = collectDisplayOptions(); // 배경색/크기 등 수집
  
  const response = await fetch('/api/perspective/wordcloud', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      batch_path: selectedBatchPath,
      perspective_type: currentDimension,
      perspective_value: perspectiveValue,
      employee_id: selectedEmployeeId || null,
      ...selectedPos,
      ...options
    })
  });
  
  // 결과 표시...
}

// ===== 그룹 일괄 생성 =====
async function generateAllGroups() {
  const options = collectOptions();
  const response = await fetch('/api/perspective/groups', {
    method: 'POST',
    ...
    body: JSON.stringify({
      batch_path: selectedBatchPath,
      perspective_type: currentDimension,
      ...options
    })
  });
  
  // 각 그룹별 WC를 그리드에 렌더링...
}
```

### 5.4 CSS 스타일

```css
/* wordcloud.html <style> 블록에 추가 */

.perspective-tabs {
  display: flex; gap: 8px; margin-bottom: 15px;
}
.perspective-tab {
  padding: 10px 20px; border: 1px solid #dee2e6;
  border-radius: 6px; cursor: pointer; background: #f8f9fa;
  font-size: 14px; transition: all 0.2s;
}
.perspective-tab.active {
  background: #007bff; color: white; border-color: #007bff;
}
.perspective-tab:hover:not(.active) {
  background: #e9ecef;
}
.stat-badge {
  display: inline-block; padding: 4px 12px;
  border-radius: 12px; font-size: 13px; margin-right: 8px;
  background: #e9ecef;
}
.stat-badge.positive { background: #d4edda; color: #155724; }
.stat-badge.negative { background: #f8d7da; color: #721c24; }
.group-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px; margin-top: 15px;
}
.group-card {
  border: 1px solid #dee2e6; border-radius: 8px;
  padding: 15px; background: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.group-card h4 {
  margin: 0 0 10px 0; font-size: 15px;
  border-bottom: 2px solid #007bff; padding-bottom: 5px;
}
.group-wc-thumb { width: 100%; border-radius: 4px; }
.group-card.warning { border-color: #ffc107; }
.group-card.warning h4 { border-color: #ffc107; }
.warning-badge {
  background: #fff3cd; color: #856404;
  padding: 8px; border-radius: 4px; font-size: 13px;
  text-align: center;
}
```

### 5.5 기존 wordcloud.html과의 통합 포인트

| 기존 요소 | 확장 방식 |
|-----------|---------|
| `#batchTree` (배치 선택) | 배치 선택 시 `selectedBatchPath` 저장 + `loadPerspectiveValues()` 호출 |
| `#metadataTree` (직원 선택) | 직원 선택 시 `selectedEmployeeId` 저장 |
| `#wordcloudOptions` | 그대로 유지 (POS, 배경색, 크기 옵션 재사용) |
| `#regenerateBtn` | 그대로 유지 (기존 개인 WC 생성 유지) |
| 새 `#perspectiveSection` | `#wordcloudOptions` 아래에 추가 |

---

## 6. 변경 파일 목록

### 6.1 신규 파일

| 파일 | 설명 | 예상 라인 |
|------|------|----------|
| `src/services/perspective_service.py` | perspective 관련 모든 서비스 함수 | ~250줄 |
| `src/routes/perspective_routes.py` | 3개 API 엔드포인트 | ~80줄 |

### 6.2 수정 파일

| 파일 | 변경 내용 | 예상 라인 |
|------|---------|----------|
| `src/services/wordcloud_service.py` | `load_batch_summary()` 유틸 추가 | +15줄 |
| `web/templates/wordcloud.html` | Perspective 탭 + 그리드 HTML + JS 추가 | +300줄 |
| `web/app.py` | perspective_bp 블루프린트 등록 | +2줄 |

### 6.3 신규 의존성 (불필요)

> 추가 Python 패키지 불필요. 기존 `wordcloud`, `matplotlib`, `Counter`만 사용.

---

## 7. 엣지 케이스

### 7.1 데이터 부족

| 상황 | 처리 |
|------|------|
| 필터링 결과 평가 0개 | `{"success": false, "error": "필터링된 평가가 없습니다."}` |
| 필터링 결과 평가 1~2개 | WC 생성은 하지만 경고 메시지 포함. 그룹 일괄 생성 시 skip |
| 필터링 결과 단어 0개 | `extract_words_from_evaluations()`에서 빈 dict 반환 → 생성 skip |
| batch_summary.json 없음 | `load_batch_summary()`가 None 반환 → 404 에러 |

### 7.2 값 그룹화

- `evaluator_position`: 이미 정형화된 값 (사원/대리/과장/차장/부장)
- `evaluator_department`: CSV에 있는 모든 부서가 동적으로 그룹화됨
- `year`: `evaluation_date`에서 `[:4]` 추출. 연도가 없는 평가는 skip

### 7.3 감정 점수 특이사항

- dimension='year'로 필터링한 경우 → 같은 단어라도 연도별 감정 맥락이 다를 수 있음
- 예: "'개선'이라는 단어가 2025년에는 부정(score=-0.5), 2026년에는 긍정(score=+0.3)"
- → evaluate 시점의 감정 분석 결과를 그대로 사용하므로 자연스러운 현상

### 7.4 이미지 파일 중복

- 동일 파라미터로 재생성 시 매번 새 파일 생성 (타임스탬프 기반)
- 기존 파일은 `outputs/`에 누적 (디스크 사용량 모니터링 필요)
- LRU 캐시 또는 주기적 정리는 추후 Phase에서 도입 가능

---

## 부록: 함수 구현 우선순위

```
1일차:
  [x] load_batch_summary()          — wordcloud_service.py
  [x] filter_evaluations_across_employees()
  [x] extract_words_from_evaluations()

2일차:
  [x] calculate_word_scores_from_evaluations()
  [x] get_available_perspective_values()
  [x] generate_perspective_wordcloud() — 단일 WC 생성

3일차:
  [x] generate_grouped_wordclouds() — 그룹 일괄 생성
  [x] perspective_routes.py (3개 API)

4일차:
  [x] wordcloud.html 확장 (탭 + 그리드 + JS)
  [x] app.py 블루프린트 등록
  [x] 통합 테스트
```
