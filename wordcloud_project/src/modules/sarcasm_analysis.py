#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import pickle
import torch
from typing import Dict, Any, Optional
from transformers import AutoTokenizer, AutoModelForSequenceClassification

class SarcasmAnalysis:
    """반어법 분석 모듈 (Transformers 기반 fine-tuning 모델 지원)"""

    def __init__(self, config_path: Optional[str] = None):
        """반어법 분석기 초기화"""
        self.config = None
        self.model = None
        self.tokenizer = None
        self.scikit_model = None
        self.vectorizer = None

        # 설정 파일 로드
        if config_path is None:
            from src.config.settings import SARCASM_CONFIG_PATH
            config_path = SARCASM_CONFIG_PATH
            print(f"기본 설정 파일 사용: {config_path}")

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            print(f"설정 파일 로드 완료: {config_path}")
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            self.config = None

        # 모델 초기화
        self._load_models()

        if self.model is None and self.scikit_model is None:
            print("사용 가능한 반어법 분석 모델이 없습니다. 반어법 분석 기능이 비활성화됩니다.")

    def _load_models(self):
        """모델 로드"""
        # Transformers 모델 로드 (우선순위)
        if self.config and self.config.get('model', {}).get('use_fine_tuned', False):
            fine_tuned_path = self.config['model']['fine_tuned_path']
            if not os.path.isabs(fine_tuned_path):
                # 상대 경로인 경우 프로젝트 루트 기준으로 변환
                # __file__은 modules/sarcasm_analysis.py이므로, 상위 디렉토리가 프로젝트 루트
                project_root = os.path.dirname(os.path.dirname(__file__))
                fine_tuned_path = os.path.join(project_root, fine_tuned_path)

            print(f"Fine-tuning 모델 경로 확인: {fine_tuned_path}")
            print(f"파일 존재: {os.path.exists(fine_tuned_path)}")

            if os.path.exists(fine_tuned_path):
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(fine_tuned_path)
                    self.model = AutoModelForSequenceClassification.from_pretrained(fine_tuned_path)
                    # CUDA 사용 가능하면 GPU로 이동
                    if torch.cuda.is_available():
                        self.model = self.model.to('cuda')
                        print("Transformers 모델을 CUDA GPU로 이동했습니다.")
                    print("Transformers fine-tuning 모델 로드 완료")
                    return
                except Exception as e:
                    print(f"Transformers 모델 로드 실패: {e}")

        # 기본 모델 로드 (fallback)
        if self.config and 'model' in self.config:
            base_path = self.config['model']['base_path']
            if not os.path.isabs(base_path):
                project_root = os.path.dirname(os.path.dirname(__file__))
                base_path = os.path.join(project_root, base_path)

            if os.path.exists(base_path):
                try:
                    self.tokenizer = AutoTokenizer.from_pretrained(base_path)
                    self.model = AutoModelForSequenceClassification.from_pretrained(base_path)
                    if torch.cuda.is_available():
                        self.model = self.model.to('cuda')
                    print("Transformers 기본 모델 로드 완료")
                    return
                except Exception as e:
                    print(f"Transformers 기본 모델 로드 실패: {e}")

        # Scikit-learn 모델 로드 (fallback)
        model_path = os.path.join(os.path.dirname(__file__), "..", "fine_tune", "sarcasm_model.pkl")
        print(f"Scikit-learn 모델 경로 확인: {model_path}")
        print(f"파일 존재: {os.path.exists(model_path)}")
        if os.path.exists(model_path):
            try:
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    self.scikit_model = model_data['model']
                    self.vectorizer = model_data['vectorizer']
                    print("Scikit-learn sarcasm 모델 로드 완료")
            except Exception as e:
                print(f"Scikit-learn 모델 로드 실패: {e}")

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        텍스트 반어법 분석

        Args:
            text: 분석할 텍스트

        Returns:
            분석 결과 딕셔너리
        """
        print(f"반어법 분석 시작: {len(text)}자")

        results = {
            "input_text": text,
            "analysis": {}
        }

        # Transformers 모델 분석 (우선순위)
        if self.model and self.tokenizer:
            try:
                # 토크나이징
                inputs = self.tokenizer(
                    text,
                    return_tensors='pt',
                    truncation=True,
                    padding=True,
                    max_length=128
                )

                # GPU 사용 시 텐서 이동
                if torch.cuda.is_available():
                    inputs = {k: v.to('cuda') for k, v in inputs.items()}

                # 예측
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits
                    probabilities = torch.softmax(logits, dim=1)[0]
                    prediction = torch.argmax(probabilities).item()

                # 결과 매핑 - threshold 적용 (Sarcasm인 경우 0.6 이상일 때만 반어법으로 인정)
                labels = self.config.get('labels', {}) if self.config else {}
                label_names = [labels.get(f'LABEL_{i}', f'LABEL_{i}') for i in range(len(probabilities))]

                # 기본 label은 Non-Sarcasm으로 가정 (LABEL_0이 Non-Sarcasm, LABEL_1이 Sarcasm)
                predicted_label = label_names[0]  # Non-Sarcasm
                confidence = probabilities[0].item()

                # Sarcasm 확률이 threshold 이상일 때만 반어법으로 인정
                sarcasm_index = 1  # LABEL_1이 Sarcasm
                threshold = self.config.get('threshold', 0.5)
                if probabilities[sarcasm_index].item() >= threshold:
                    predicted_label = label_names[sarcasm_index]
                    confidence = probabilities[sarcasm_index].item()
                else:
                    # Non-Sarcasm일 경우, Non-Sarcasm 확률을 confidence로 사용
                    predicted_label = label_names[0]
                    confidence = probabilities[0].item()

                results["analysis"]["fine_tuned_result"] = {
                    "mapped": {
                        "label": predicted_label,
                        "confidence": float(confidence)
                    },
                    "raw": {
                        "label": f"LABEL_{prediction}",
                        "score": float(confidence)
                    },
                    "probabilities": {
                        label_names[i]: float(probabilities[i]) for i in range(len(probabilities))
                    }
                }

                print(f"Transformers 모델 분석 완료: {predicted_label} (신뢰도: {confidence:.4f})")

            except Exception as e:
                results["analysis"]["fine_tuned_result"] = {"error": str(e)}
                print(f"Transformers 모델 분석 실패: {e}")

        # Scikit-learn 모델 분석 (fallback)
        elif self.scikit_model and self.vectorizer:
            try:
                # 텍스트 벡터화
                text_vectorized = self.vectorizer.transform([text])

                # 예측
                prediction_proba = self.scikit_model.predict_proba(text_vectorized)[0]
                prediction = self.scikit_model.predict(text_vectorized)[0]

                # 결과 매핑 - threshold 적용 (Sarcasm인 경우 0.6 이상일 때만 반어법으로 인정)
                label_names = ["Non-Sarcasm", "Sarcasm"]
                predicted_label = label_names[0]  # 기본 Non-Sarcasm
                confidence = prediction_proba[0]

                # Sarcasm 확률이 threshold 이상일 때만 반어법으로 인정
                sarcasm_index = 1
                threshold = self.config.get('threshold', 0.5)
                if prediction_proba[sarcasm_index] >= threshold:
                    predicted_label = label_names[sarcasm_index]
                    confidence = prediction_proba[sarcasm_index]
                else:
                    # Non-Sarcasm일 경우, Non-Sarcasm 확률을 confidence로 사용
                    predicted_label = label_names[0]
                    confidence = prediction_proba[0]

                results["analysis"]["sklearn_result"] = {
                    "mapped": {
                        "label": predicted_label,
                        "confidence": float(confidence)
                    },
                    "probabilities": {
                        "Non-Sarcasm": float(prediction_proba[0]),
                        "Sarcasm": float(prediction_proba[1])
                    }
                }

                print(f"Scikit-learn 모델 분석 완료: {predicted_label} (신뢰도: {confidence:.4f})")

            except Exception as e:
                results["analysis"]["sklearn_result"] = {"error": str(e)}
                print(f"Scikit-learn 모델 분석 실패: {e}")

        # 모델이 없을 경우 기본 결과 반환
        if not self.model and not self.scikit_model:
            results["analysis"] = {
                "fine_tuned_result": {
                    "mapped": {
                        "label": "Non-Sarcasm",
                        "confidence": 0.0
                    }
                },
                "sklearn_result": {
                    "mapped": {
                        "label": "Non-Sarcasm",
                        "confidence": 0.0
                    }
                }
            }
        
        print("반어법 분석 완료")
        return results

# 싱글톤 인스턴스 저장
_sarcasm_analyzer_instance = None

def analyze_sarcasm(text: str) -> Dict[str, Any]:
    """
    편의 함수: 반어법 분석

    Args:
        text: 분석할 텍스트

    Returns:
        분석 결과
    """
    global _sarcasm_analyzer_instance
    if _sarcasm_analyzer_instance is None:
        _sarcasm_analyzer_instance = SarcasmAnalysis()
    return _sarcasm_analyzer_instance.analyze(text)
