#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import time
from typing import Dict, Any, Optional, List
from utils.logger import setup_logger, get_log_file_path, get_timestamp

# 외부 라이브러리 import
try:
    from korcen import Korcen  # 한국어 욕설 필터링
    KORCEN_AVAILABLE = True
except ImportError:
    KORCEN_AVAILABLE = False

try:
    from profanity_check import predict_prob  # 영어 욕설 필터링
    PROFANITY_CHECK_AVAILABLE = True
except ImportError:
    PROFANITY_CHECK_AVAILABLE = False

class ProfanityFilter:
    """비속어 및 불용어 필터링 모듈"""

    def __init__(self, config_path: str = "configs/profanity_config.json"):
        """
        비속어 필터 초기화

        Args:
            config_path: 설정 파일 경로
        """
        self.config = self._load_config(config_path)
        self.timestamp = get_timestamp()

        # 로거 설정
        log_file = get_log_file_path(self.config["module_name"], self.timestamp)
        self.logger = setup_logger(self.config["module_name"], log_file)

        # 필터 리스트 로드
        self.profanity_words = self.config.get("profanity_words", [])
        self.stop_words = self.config.get("stop_words", [])
        self.unhealthy_words = self.config.get("unhealthy_words", [])

        # 외부 라이브러리 초기화
        self.korcen = Korcen() if KORCEN_AVAILABLE else None
        self.profanity_check_available = PROFANITY_CHECK_AVAILABLE

        self.logger.info("비속어 필터 초기화 완료")
        if KORCEN_AVAILABLE:
            self.logger.info("Korcen 라이브러리 로드됨")
        if PROFANITY_CHECK_AVAILABLE:
            self.logger.info("profanity-check 라이브러리 로드됨")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 기본 설정
            return {
                "module_name": "profanity_filter",
                "profanity_words": [
                    "시발", "씨발", "병신", "개새끼", "좆", "좃", "씹", "쌍놈", "쌍년", "새끼", "년", "놈",
                    "미친", "미친놈", "미친년", "개년", "개놈", "지랄", "지랄놈", "지랄년", "fuck", "shit",
                    "damn", "bitch", "asshole", "bastard", "cunt", "dick", "pussy"
                ],
                "stop_words": [
                    "이", "그", "저", "것", "수", "등", "에서", "에게", "으로", "에서", "이다", "하다",
                    "있다", "없다", "되다", "아니다", "이다", "것이다", "수 있다", "할 수 있다"
                ],
                "unhealthy_words": [
                    "섹스", "성관계", "포르노", "야동", "자위", "오르가즘", "사정", "음경", "보지",
                    "가슴", "젖", "엉덩이", "sex", "porn", "masturbate", "orgasm", "penis", "vagina",
                    "breast", "butt", "ass"
                ],
                "remove_special_chars": True,
                "output": {
                    "save_results": True
                }
            }

    def filter_text(self, text: str, remove_profanity: bool = True,
                   remove_stop_words: bool = True, remove_unhealthy: bool = True,
                   remove_special_chars: bool = True) -> Dict[str, Any]:
        """
        텍스트 필터링

        Args:
            text: 필터링할 텍스트
            remove_profanity: 욕설 제거 여부
            remove_stop_words: 불용어 제거 여부
            remove_unhealthy: 비건전 단어 제거 여부
            remove_special_chars: 특수문자 제거 여부

        Returns:
            필터링 결과 딕셔너리
        """
        self.logger.info(f"텍스트 필터링 시작: {len(text)}자")

        start_time = time.time()
        original_text = text
        removed_items = []

        # 특수문자 제거
        if remove_special_chars:
            # 한글, 영문, 숫자, 공백만 남기고 제거
            text = re.sub(r'[^\w\s가-힣]', '', text)
            if text != original_text:
                removed_items.append("특수문자")

        # 욕설 제거
        if remove_profanity:
            for word in self.profanity_words:
                if word in text:
                    text = text.replace(word, "***")
                    removed_items.append(f"욕설:{word}")

        # 비건전 단어 제거
        if remove_unhealthy:
            for word in self.unhealthy_words:
                if word in text:
                    text = text.replace(word, "***")
                    removed_items.append(f"비건전:{word}")

        # 불용어 제거 (단어 단위로 처리)
        if remove_stop_words:
            words = text.split()
            filtered_words = []
            for word in words:
                if word not in self.stop_words:
                    filtered_words.append(word)
                else:
                    removed_items.append(f"불용어:{word}")
            text = ' '.join(filtered_words)

        processing_time = int((time.time() - start_time) * 1000)

        result = {
            "original_text": original_text,
            "filtered_text": text,
            "original_length": len(original_text),
            "filtered_length": len(text),
            "removed_items": list(set(removed_items)),  # 중복 제거
            "processing_time_ms": processing_time
        }

        self.logger.info(f"텍스트 필터링 완료: {len(removed_items)}개 항목 제거, {processing_time}ms 소요")

        return result

    def detect_language(self, text: str) -> str:
        """
        텍스트 언어 감지

        Args:
            text: 분석할 텍스트

        Returns:
            언어 코드 ("ko": 한국어, "en": 영어, "mixed": 혼합, "unknown": 알 수 없음)
        """
        # 한글 문자 수
        korean_chars = len(re.findall(r'[가-힣]', text))
        # 영어 문자 수
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        # 총 알파벳 수
        total_chars = len(text.replace(' ', ''))

        if total_chars == 0:
            return "unknown"

        korean_ratio = korean_chars / total_chars
        english_ratio = english_chars / total_chars

        if korean_ratio > 0.7:
            return "ko"
        elif english_ratio > 0.7:
            return "en"
        elif korean_chars > 0 and english_chars > 0:
            return "mixed"
        else:
            return "unknown"

    def advanced_filter_text(self, text: str, context: str = None) -> Dict[str, Any]:
        """
        고급 필터링: korcen + profanity-check + 기존 필터 통합

        Args:
            text: 필터링할 텍스트
            context: 처리 상황 컨텍스트 (예: "👤 대상자 ID: U002, 평가 ID: 1")

        Returns:
            고급 필터링 결과
        """
        log_prefix = context if context else ""
        if log_prefix:
            log_prefix = f"{log_prefix} | "
            
        self.logger.info(f"{log_prefix}고급 텍스트 필터링 시작: {len(text)}자")

        start_time = time.time()
        original_text = text
        detected_profanity = []
        filtered_text = text
        methods_used = []

        # 언어 감지
        language = self.detect_language(text)
        self.logger.info(f"{log_prefix}감지된 언어: {language}")

        # 한국어 텍스트 필터링 (korcen)
        if language in ["ko", "mixed"] and self.korcen:
            try:
                # korcen 필터링 적용
                korcen_result = self.korcen.filter(text)
                if korcen_result != text:
                    # korcen이 감지한 비속어 단어 추출 (간단한 방법)
                    import difflib
                    s = difflib.SequenceMatcher(None, text, korcen_result)
                    for tag, i1, i2, j1, j2 in s.get_opcodes():
                        if tag == 'replace' and korcen_result[j1:j2] == '***':
                            detected_profanity.append(text[i1:i2])
                    filtered_text = korcen_result
                    methods_used.append("korcen")
                    self.logger.info(f"{log_prefix}Korcen 필터링 적용됨")
            except Exception as e:
                self.logger.warning(f"{log_prefix}Korcen 필터링 실패: {e}")

        # 영어 텍스트 필터링 (profanity-check)
        if language in ["en", "mixed"] and self.profanity_check_available:
            try:
                # profanity-check로 욕설 확률 계산
                prob = predict_prob([text])[0]
                if prob > 0.8:  # 80% 이상 욕설로 판단
                    # 간단한 마스킹 (더 정교한 방법 필요시 개선)
                    words = text.split()
                    for i, word in enumerate(words):
                        if len(word) > 3:  # 짧은 단어 제외
                            word_prob = predict_prob([word])[0]
                            if word_prob > 0.9:
                                words[i] = "***"
                                detected_profanity.append(word)
                    filtered_text = ' '.join(words)
                    methods_used.append("profanity_check")
                    self.logger.info(f"{log_prefix}profanity-check 필터링 적용됨")
            except Exception as e:
                self.logger.warning(f"{log_prefix}profanity-check 필터링 실패: {e}")

        # 기존 필터 보완 (한글/영어 공통 욕설) - 원본 텍스트에 대해 적용
        for word in self.profanity_words:
            if word in original_text:
                filtered_text = filtered_text.replace(word, "***")
                detected_profanity.append(word)

        # 워드클라우드용 최적화: 특수문자/불용어 제거 생략
        # (형태소 분석에서 처리되므로 여기서는 skip)

        processing_time = int((time.time() - start_time) * 1000)

        result = {
            "original_text": original_text,
            "filtered_text": filtered_text,
            "language": language,
            "detected_profanity": list(set(detected_profanity)),
            "methods_used": methods_used,
            "profanity_count": len(detected_profanity),
            "processing_time_ms": processing_time
        }

        self.logger.info(f"{log_prefix}고급 필터링 완료: {len(detected_profanity)}개 욕설 검출, {processing_time}ms 소요")

        return result

# 싱글톤 인스턴스 저장
_profanity_filter_instance = None

def filter_profanity(text: str, remove_profanity: bool = True,
                    remove_stop_words: bool = True, remove_unhealthy: bool = True,
                    remove_special_chars: bool = True,
                    config_path: str = "configs/profanity_config.json") -> Dict[str, Any]:
    """
    편의 함수: 기본 텍스트 필터링

    Args:
        text: 필터링할 텍스트
        remove_profanity: 욕설 제거 여부
        remove_stop_words: 불용어 제거 여부
        remove_unhealthy: 비건전 단어 제거 여부
        remove_special_chars: 특수문자 제거 여부
        config_path: 설정 파일 경로

    Returns:
        필터링 결과
    """
    global _profanity_filter_instance
    if _profanity_filter_instance is None:
        _profanity_filter_instance = ProfanityFilter(config_path)
    return _profanity_filter_instance.filter_text(text, remove_profanity, remove_stop_words,
                                                 remove_unhealthy, remove_special_chars)


def advanced_filter_profanity(text: str, config_path: str = "configs/profanity_config.json", context: str = None) -> Dict[str, Any]:
    """
    편의 함수: 고급 텍스트 필터링 (korcen + profanity-check 통합)

    Args:
        text: 필터링할 텍스트
        config_path: 설정 파일 경로
        context: 처리 상황 컨텍스트 (예: "👤 대상자 ID: U002, 평가 ID: 1")

    Returns:
        고급 필터링 결과
    """
    global _profanity_filter_instance
    if _profanity_filter_instance is None:
        _profanity_filter_instance = ProfanityFilter(config_path)
    return _profanity_filter_instance.advanced_filter_text(text, context)
