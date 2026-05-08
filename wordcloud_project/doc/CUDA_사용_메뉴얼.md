# Qwen 모델 CUDA 사용 메뉴얼

## 개요
이 메뉴얼은 Qwen3-8B-Korean-Sentiment 모델을 사용할 때 CUDA( GPU 가속)을 활성화하는 방법을 설명합니다. CUDA를 사용하면 모델 로딩 및 추론 속도가 크게 향상됩니다.

## CUDA 설치 확인
### 1. CUDA Toolkit 설치 확인
```bash
nvcc --version
```
- CUDA Toolkit 11.8 이상이 설치되어 있어야 합니다.
- 없으면 NVIDIA 홈페이지에서 다운로드 및 설치: [CUDA Toolkit](https://developer.nvidia.com/cuda-toolkit-archive)

### 2. PyTorch CUDA 버전 확인
```bash
python -c "import torch; print('Torch version:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('CUDA version:', torch.version.cuda)"
```
- CUDA가 사용 가능한지 확인합니다. (`CUDA available: True`)
- PyTorch 버전이 CUDA Toolkit 버전과 호환되어야 합니다.

## Qwen 모델 CUDA 설정

### 1. test_qwen_model.py CUDA 설정
```python
# wordcloud_project/test_qwen_model.py

def test_qwen_model():
    try:
        model_path = "D:/dev/wordcloud/model/Qwen3-8B-Korean-Sentiment"
        
        model = AutoPeftModelForCausalLM.from_pretrained(
            model_path,
            device_map="cuda",  # GPU 할당 방법 지정
            torch_dtype=torch.bfloat16,  # 데이터 타입 지정
            trust_remote_code=True,
            local_files_only=True
        )
        
        print(f"CUDA 사용 가능: {torch.cuda.is_available()}")
        print(f"모델 디바이스: {next(model.parameters()).device}")
        
        # 토크나이징
        inputs = tokenizer(prompt, return_tensors="pt")
        
        # GPU로 텐서 이동
        with torch.no_grad():
            outputs = model.generate(
                input_ids=inputs["input_ids"].to("cuda"),  # GPU로 이동
                max_new_tokens=512
            )
```

### 2. compare_sentiment_models.py CUDA 설정
```python
# wordcloud_project/compare_sentiment_models.py

class SentimentModelComparator:
    def _init_qwen_model(self):
        self.qwen_model = AutoPeftModelForCausalLM.from_pretrained(
            model_path,
            device_map="cuda",  # GPU 할당 방법 지정
            torch_dtype=torch.bfloat16,  # 데이터 타입 지정
            trust_remote_code=True,
            local_files_only=True
        )
    
    def analyze_with_qwen(self, text: str) -> Dict[str, Any]:
        inputs = self.qwen_tokenizer(prompt, return_tensors="pt")
        
        with torch.no_grad():
            outputs = self.qwen_model.generate(
                input_ids=inputs["input_ids"].to("cuda"),  # GPU로 이동
                max_new_tokens=512
            )
```

## CUDA 사용 문제 해결

### 문제 1: CUDA 사용 불가 (CUDA available: False)
- **원인**: PyTorch CUDA 버전이 설치되지 않았거나, CUDA Toolkit과 호환되지 않음
- **해결 방법**:
  ```bash
  pip uninstall torch torchvision torchaudio
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
  ```
  - CUDA Toolkit 11.8에 맞는 PyTorch 버전을 설치합니다.

### 문제 2: Out of Memory (OOM) 오류
- **원인**: GPU 메모리가 부족함
- **해결 방법**:
  1. `torch_dtype`을 `torch.float16`으로 변경 (메모리 사용량 감소)
  2. `max_new_tokens`를 줄여서 생성 토큰 수 제한
  3. `device_map="auto"`로 자동 메모리 관리
  4. 더 큰 메모리의 GPU 사용

### 문제 3: 모델 로딩 실패
- **원인**: `local_files_only=True`로 인해 Hugging Face Hub에서 모델을 다운로드할 수 없음
- **해결 방법**:
  - `local_files_only=False`로 변경하거나, 모델을 로컬에 다운로드한 후 사용

## CUDA 성능 최적화

### 1. 데이터 타입 최적화
```python
# FP16으로 모델 로딩 (메모리 사용량 50% 감소)
model = AutoPeftModelForCausalLM.from_pretrained(
    model_path,
    device_map="cuda",
    torch_dtype=torch.float16,
    trust_remote_code=True,
    local_files_only=True
)
```

### 2. 메모리 관리
```python
import torch

# CUDA 캐시 클리어
torch.cuda.empty_cache()

# 모델 파기
del model
```

### 3. 배치 처리
```python
# 배치로 추론 (GPU 사용률 높임)
inputs = tokenizer(batch_texts, padding=True, truncation=True, return_tensors="pt")
outputs = model.generate(
    input_ids=inputs["input_ids"].to("cuda"),
    attention_mask=inputs["attention_mask"].to("cuda"),
    max_new_tokens=512
)
```

## 테스트 예시

### CUDA 확인 테스트
```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"CUDA device count: {torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"CUDA device name: {torch.cuda.get_device_name()}")
```

### Qwen 모델 CUDA 사용 테스트
```bash
cd wordcloud_project
python test_qwen_model.py
```

## 주의事项

1. CUDA Toolkit과 PyTorch CUDA 버전이 호환되어야 합니다.
2. GPU 메모리가 충분히 있어야 합니다. (Qwen3-8B는 약 8GB 이상 필요)
3. `device_map` 매개변수를 적절히 설정하여 GPU 메모리를 효율적으로 사용합니다.
4. 모델 추론 후 CUDA 캐시를 클리어하여 메모리 리스크를 줄입니다.