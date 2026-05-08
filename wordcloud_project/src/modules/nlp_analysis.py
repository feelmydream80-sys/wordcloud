#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import threading
from typing import Dict, Any, Optional
from kiwipiepy import Kiwi
from konlpy.tag import Okt
from utils.logger import setup_logger, get_log_file_path, get_timestamp

class NLPAnalysis:
    """자연어 형태소 분석 모듈"""

    _instances = {}
    _lock = threading.Lock()

    def __init__(self, config_path: str = "configs/nlp_config.json"):
        """
        NLP 분석기 초기화

        Args:
            config_path: 설정 파일 경로
        """
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.timestamp = get_timestamp()

        # 로거 설정
        log_file = get_log_file_path(self.config["module_name"], self.timestamp)
        self.logger = setup_logger(self.config["module_name"], log_file)

        # 분석기 초기화
        self.kiwi = Kiwi() if self.config["kiwi"]["enabled"] else None
        self.okt = Okt() if self.config["okt"]["enabled"] else None

        self.logger.info("NLP 분석기 초기화 완료")

    @classmethod
    def get_instance(cls, config_path: str = "configs/nlp_config.json"):
        """싱글톤 인스턴스 반환 (Thread-safe)"""
        if config_path not in cls._instances:
            with cls._lock:
                if config_path not in cls._instances:
                    cls._instances[config_path] = cls(config_path)
        return cls._instances[config_path]

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def analyze(self, text: str, output_path: Optional[str] = None, context: str = None) -> Dict[str, Any]:
        """
        텍스트 형태소 분석

        Args:
            text: 분석할 텍스트
            output_path: 결과 저장 경로 (None이면 저장 안함)
            context: 처리 상황 컨텍스트 (예: "👤 대상자 ID: U002, 평가 ID: 1")

        Returns:
            분석 결과 딕셔너리
        """
        log_prefix = context if context else ""
        if log_prefix:
            log_prefix = f"{log_prefix} | "
            
        self.logger.info(f"{log_prefix}텍스트 분석 시작: {len(text)}자")

        results = {
            "input_text": text,
            "analysis": {}
        }

        # Kiwi 분석
        if self.kiwi:
            try:
                kiwi_result = self.kiwi.analyze(text)
                # Kiwi 결과는 (tokens, score) 튜플 형태
                if isinstance(kiwi_result, tuple) and len(kiwi_result) >= 1:
                    tokens = kiwi_result[0]
                    kiwi_results = []
                    for token in tokens:
                        kiwi_results.append({
                            "form": token.form,
                            "tag": token.tag,
                            "start": token.start,
                            "len": token.len
                        })
                    results["analysis"]["kiwi_tokens"] = kiwi_results
                    self.logger.info(f"{log_prefix}Kiwi 분석 완료")
                else:
                    results["analysis"]["kiwi_tokens"] = {"error": "Unexpected result format"}
            except Exception as e:
                self.logger.error(f"{log_prefix}Kiwi 분석 실패: {e}")
                results["analysis"]["kiwi_tokens"] = {"error": str(e)}

        # Okt 분석
        if self.okt:
            try:
                # 형태소 분석 및 품사 태깅
                okt_pos = self.okt.pos(text)

                # wordcloud_pos 설정에 따라 의미 있는 단어 추출
                wordcloud_pos = self.config.get('wordcloud_pos', ['Noun', 'Verb', 'Adjective'])
                meaningful_words = []
                from src.modules.stopword_manager import get_stopword_manager
                manager = get_stopword_manager()
                for word, pos in okt_pos:
                    # 설정된 품사만 추출
                    if pos in wordcloud_pos and len(word) > 1:
                        # 불용어 제거
                        if not manager.is_stopword(word):
                            meaningful_words.append((word, pos))
                    elif len(word) == 1:
                        # 한 글자 단어는 불용어로 간주 (설정된 리스트 외에도)
                        if not manager.is_stopword(word):
                            meaningful_words.append((word, pos))

                # 문장 경계 추출
                sentence_boundaries = self._extract_sentence_boundaries(text)

                # meaningful_words에서 품사 태그 제거 (단어만 반환)
                words_only = [word for word, pos in meaningful_words]
                results["analysis"]["okt_morphemes"] = okt_pos  # 전체 형태소 (품사 포함)
                results["analysis"]["meaningful_words"] = words_only  # 의미 있는 단어만 (품사 제거)
                # 품사 정보가 필요한 경우 별도로 저장
                results["analysis"]["meaningful_words_with_pos"] = meaningful_words
                results["analysis"]["sentence_boundaries"] = sentence_boundaries

                self.logger.info(f"{log_prefix}Okt 분석 완료: {len(meaningful_words)}개 의미 단어 추출 (품사: {wordcloud_pos})")
            except Exception as e:
                self.logger.error(f"{log_prefix}Okt 분석 실패: {e}")
                results["analysis"]["okt_morphemes"] = {"error": str(e)}
                results["analysis"]["meaningful_words"] = {"error": str(e)}
                results["analysis"]["sentence_boundaries"] = {"error": str(e)}

        # 결과 저장
        if output_path and self.config["output"]["save_results"]:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            self.logger.info(f"{log_prefix}결과 저장 완료: {output_path}")

        self.logger.info(f"{log_prefix}텍스트 분석 완료")
        results["config"] = self.config
        return results

    def analyze_word_pos(self, word: str) -> str:
        """
        단어의 품사 분석 (Okt 사용)

        Args:
            word: 분석할 단어

        Returns:
            품사 태그
        """
        try:
            if self.okt:
                pos_result = self.okt.pos(word)
                if pos_result:
                    print(f"품사 분석 결과 (Okt): {pos_result}")  # 디버그 로그
                    return pos_result[0][1]  # (word, pos) 튜플에서 pos 반환
            else:
                print("Okt 분석기가 활성화되지 않았습니다.")
        except Exception as e:
            print(f"단어 품사 분석 실패: {word} - {e}")
            import traceback
            print(f"스택 트레이스: {traceback.format_exc()}")
            self.logger.error(f"단어 품사 분석 실패: {word} - {e}")
        
        return 'Unknown'

    def _extract_sentence_boundaries(self, text: str) -> list:
        """
        문장 경계 추출

        Args:
            text: 분석할 텍스트

        Returns:
            문장 경계 위치 리스트
        """
        boundaries = []
        current_pos = 0

        # 문장 구분자 패턴
        sentence_end_patterns = ['.', '!', '?', '。', '！', '？']

        for i, char in enumerate(text):
            if char in sentence_end_patterns:
                boundaries.append(current_pos)
                current_pos = i + 1

        # 마지막 문장 추가
        if current_pos < len(text):
            boundaries.append(current_pos)

        return boundaries

def analyze_text(text: str, config_path: str = None,
                output_path: Optional[str] = None, context: str = None) -> Dict[str, Any]:
    """
    편의 함수: 텍스트 분석

    Args:
        text: 분석할 텍스트
        config_path: 설정 파일 경로 (기본값: 프로젝트 루트의 configs/nlp_config.json)
        output_path: 결과 저장 경로
        context: 처리 상황 컨텍스트 (예: "👤 대상자 ID: U002, 평가 ID: 1")

    Returns:
        분석 결과
    """
    if config_path is None:
        from src.config.settings import NLP_CONFIG_PATH
        config_path = NLP_CONFIG_PATH
    
    analyzer = NLPAnalysis.get_instance(config_path)
    return analyzer.analyze(text, output_path, context)
