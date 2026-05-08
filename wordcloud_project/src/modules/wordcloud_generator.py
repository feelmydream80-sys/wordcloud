#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import matplotlib.pyplot as plt
from typing import Dict, Any, Optional, Callable
from wordcloud import WordCloud
from collections import Counter
import numpy as np
from utils.logger import setup_logger, get_log_file_path, get_timestamp
from src.modules.stopword_manager import get_stopword_manager, filter_stopwords

class WordCloudConfig:
    """워드클라우드 설정 관리 클래스"""

    # 미리 정의된 크기 프리셋
    SIZE_PRESETS = {
        "thumbnail": {"width": 400, "height": 300, "name": "썸네일"},
        "small": {"width": 600, "height": 400, "name": "소형"},
        "standard": {"width": 800, "height": 600, "name": "표준"},
        "large": {"width": 1000, "height": 750, "name": "대형"},
        "xlarge": {"width": 1200, "height": 900, "name": "초대형"},
        "hd": {"width": 1600, "height": 1200, "name": "고해상도"}
    }

    # 지원되는 배경색
    SUPPORTED_COLORS = ["white", "black", "lightblue", "lightgray", "lightgreen", "lightyellow", "lightpink"]

    def __init__(self, config_path: str = "configs/wordcloud_config.json"):
        self.config_path = config_path
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            # 기본 설정 생성
            return {
                "module_name": "wordcloud_generator",
                "description": "워드클라우드 생성 설정",
                "wordcloud": {
                    "font_path": "malgun.ttf",
                    "background_color": "white",
                    "width": 800,
                    "height": 600,
                    "max_words": 100
                },
                "output": {
                    "format": "png",
                    "save_image": True,
                    "show_plot": False
                }
            }

    def save_config(self):
        """설정 파일 저장"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def update_settings(self, **kwargs):
        """워드클라우드 설정 업데이트"""
        wordcloud_config = self.config.setdefault("wordcloud", {})

        # 크기 설정
        if "size_preset" in kwargs:
            preset = kwargs["size_preset"]
            if preset in self.SIZE_PRESETS:
                # 미리 정의된 프리셋 사용
                preset_data = self.SIZE_PRESETS[preset]
                wordcloud_config["width"] = preset_data["width"]
                wordcloud_config["height"] = preset_data["height"]
            elif "x" in preset:
                # "800x600" 형식 파싱
                try:
                    width, height = map(int, preset.split('x'))
                    wordcloud_config["width"] = width
                    wordcloud_config["height"] = height
                except ValueError:
                    pass

        # 개별 크기 설정
        if "width" in kwargs:
            wordcloud_config["width"] = kwargs["width"]
        if "height" in kwargs:
            wordcloud_config["height"] = kwargs["height"]

        # 배경색 설정
        if "background_color" in kwargs:
            color = kwargs["background_color"]
            if color in self.SUPPORTED_COLORS:
                wordcloud_config["background_color"] = color

        # 최대 단어 수 설정
        if "max_words" in kwargs:
            wordcloud_config["max_words"] = kwargs["max_words"]

        self.save_config()
        return wordcloud_config

    def get_size_options(self):
        """사용 가능한 크기 옵션 반환"""
        return {k: v for k, v in self.SIZE_PRESETS.items()}

    def get_color_options(self):
        """사용 가능한 색상 옵션 반환"""
        return self.SUPPORTED_COLORS

    def get_current_settings(self):
        """현재 워드클라우드 설정 반환"""
        return self.config.get("wordcloud", {})


class WordCloudGenerator:
    """워드클라우드 생성 모듈"""

    def __init__(self, config_path: str = "configs/wordcloud_config.json"):
        """
        워드클라우드 생성기 초기화

        Args:
            config_path: 설정 파일 경로
        """
        self.config_manager = WordCloudConfig(config_path)
        self.config = self.config_manager.config
        self.timestamp = get_timestamp()

        # 로거 설정
        log_file = get_log_file_path(self.config["module_name"], self.timestamp)
        self.logger = setup_logger(self.config["module_name"], log_file)

        self.logger.info("워드클라우드 생성기 초기화 완료")

    def update_config(self, **kwargs):
        """워드클라우드 설정 업데이트"""
        return self.config_manager.update_settings(**kwargs)

    def get_config_options(self):
        """설정 옵션 반환"""
        return {
            "sizes": self.config_manager.get_size_options(),
            "colors": self.config_manager.get_color_options(),
            "current": self.config_manager.get_current_settings()
        }

    def generate(self, text: str, output_path: Optional[str] = None, remove_stopwords: bool = True) -> bool:
        """
        텍스트로부터 워드클라우드 생성

        Args:
            text: 워드클라우드 생성할 텍스트
            output_path: 이미지 저장 경로 (None이면 저장 안함)
            remove_stopwords: 불용어 제거 여부

        Returns:
            성공 여부
        """
        self.logger.info(f"워드클라우드 생성 시작: {len(text)}자")

        try:
            # 불용어 제거
            processed_text = text
            if remove_stopwords:
                processed_text = filter_stopwords(text)
                self.logger.info(f"불용어 제거 완료: {len(text) - len(processed_text)}자 제거")

            # 워드클라우드 설정
            wc_config = self.config["wordcloud"]
            wordcloud = WordCloud(
                font_path=wc_config.get("font_path"),
                background_color=wc_config.get("background_color", "white"),
                width=wc_config.get("width", 800),
                height=wc_config.get("height", 600),
                max_words=wc_config.get("max_words", 100)
            )

            # 워드클라우드 생성
            wordcloud.generate(processed_text)
            self.logger.info("워드클라우드 생성 완료")

            # 이미지 저장
            if output_path and self.config["output"]["save_image"]:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                wordcloud.to_file(output_path)
                self.logger.info(f"워드클라우드 이미지 저장 완료: {output_path}")

            # 플롯 표시 (선택적)
            if self.config["output"]["show_plot"]:
                plt.figure(figsize=(10, 8))
                plt.imshow(wordcloud, interpolation='bilinear')
                plt.axis('off')
                plt.show()

            self.logger.info("워드클라우드 생성 완료")
            return True

        except Exception as e:
            self.logger.error(f"워드클라우드 생성 실패: {e}")
            return False

    def generate_wordcloud_with_options(self, text: str, output_path: Optional[str] = None,
                                       background_color: str = 'white', max_words: int = 100,
                                       width: int = 800, height: int = 600,
                                       remove_stopwords: bool = True) -> bool:
        """
        옵션을 적용한 워드클라우드 생성

        Args:
            text: 워드클라우드 생성할 텍스트
            output_path: 이미지 저장 경로
            background_color: 배경색
            max_words: 최대 단어 수
            width: 너비
            height: 높이
            remove_stopwords: 불용어 제거 여부

        Returns:
            성공 여부
        """
        self.logger.info(f"옵션 적용 워드클라우드 생성 시작: {len(text)}자")

        try:
            # 불용어 제거
            processed_text = text
            if remove_stopwords:
                processed_text = filter_stopwords(text)
                self.logger.info(f"불용어 제거 완료: {len(text) - len(processed_text)}자 제거")

            # 설정 업데이트
            self.update_config(
                background_color=background_color,
                max_words=max_words,
                width=width,
                height=height
            )

            # 워드클라우드 설정
            wc_config = self.config["wordcloud"]
            wordcloud = WordCloud(
                font_path=wc_config.get("font_path"),
                background_color=wc_config.get("background_color", "white"),
                width=wc_config.get("width", 800),
                height=wc_config.get("height", 600),
                max_words=wc_config.get("max_words", 100)
            )

            # 워드클라우드 생성
            wordcloud.generate(processed_text)
            self.logger.info("워드클라우드 생성 완료")

            # 이미지 저장
            if output_path and self.config["output"]["save_image"]:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                wordcloud.to_file(output_path)
                self.logger.info(f"워드클라우드 이미지 저장 완료: {output_path}")

            # 플롯 표시 (선택적)
            if self.config["output"]["show_plot"]:
                plt.figure(figsize=(10, 8))
                plt.imshow(wordcloud, interpolation='bilinear')
                plt.axis('off')
                plt.show()

            return True

        except Exception as e:
            self.logger.error(f"옵션 적용 워드클라우드 생성 실패: {e}")
            import traceback
            self.logger.error(f"오류 상세: {traceback.format_exc()}")
            return False

    def generate_with_colors_and_options(self, word_freq: Dict[str, float], word_scores: Dict[str, float],
                                       output_path: Optional[str] = None, background_color: str = 'white',
                                       max_words: int = 100, width: int = 800, height: int = 600,
                                       remove_stopwords: bool = True) -> bool:
        """
        옵션을 적용한 감정 기반 색상 워드클라우드 생성

        Args:
            word_freq: 단어 빈도 딕셔너리
            word_scores: 단어 별 감정 점수 딕셔너리 (양수: 긍정, 음수: 부정, 0: 중립)
            output_path: 이미지 저장 경로
            background_color: 배경색
            max_words: 최대 단어 수
            width: 너비
            height: 높이
            remove_stopwords: 불용어 제거 여부

        Returns:
            성공 여부
        """
        self.logger.info(f"옵션 적용 감정 기반 워드클라우드 생성 시작: {len(word_freq)}개 단어")

        try:
            # 불용어 제거
            processed_word_freq = word_freq.copy()
            if remove_stopwords:
                manager = get_stopword_manager()
                for word in list(processed_word_freq.keys()):
                    if manager.is_stopword(word):
                        del processed_word_freq[word]
                self.logger.info(f"불용어 제거 완료: {len(word_freq) - len(processed_word_freq)}개 단어 제거")

            # 설정 업데이트
            self.update_config(
                background_color=background_color,
                max_words=max_words,
                width=width,
                height=height
            )

            # 단어 빈도 검증
            if not processed_word_freq or len(processed_word_freq) == 0:
                self.logger.error("단어 빈도 정보가 없습니다.")
                return False

            # 색상 함수 (감정 점수 기반)
            def color_func(word, font_size, position, orientation, random_state=None, **kwargs):
                score = word_scores.get(word, 0.0)
                
                # score에 따라 색상 결정
                if score > 0.5:
                    # 강한 긍정: 민트 파스텔 (152, 251, 152)
                    base_color = [152, 251, 152]
                elif score > 0.0:
                    # 약한 긍정: 연한 민트 (224, 255, 224)
                    base_color = [224, 255, 224]
                elif score >= -0.5 and score <= 0.0:
                    # 중립: 파스텔 회색 (240, 240, 240)
                    base_color = [240, 240, 240]
                elif score > -0.5:
                    # 약한 부정: 연한 파스텔 빨강 (255, 228, 225)
                    base_color = [255, 228, 225]
                else:
                    # 강한 부정: 파스텔 빨강 (250, 128, 114)
                    base_color = [250, 128, 114]
                
                # 점수의 절대값에 따라 진하기 조절
                normalized_score = max(-1.0, min(1.0, score))
                intensity = abs(normalized_score)
                
                # intensity에 따라 색상의 명도 조절 (0.7~1.0 범위)
                if intensity == 0:
                    color = [200, 200, 200]
                else:
                    brightness = 0.7 + (intensity * 0.3)
                    color = [int(c * brightness) for c in base_color]
                
                return tuple(color)

            # 워드클라우드 설정
            wc_config = self.config["wordcloud"]
            wordcloud = WordCloud(
                font_path=wc_config.get("font_path"),
                background_color=wc_config.get("background_color", "white"),
                width=wc_config.get("width", 800),
                height=wc_config.get("height", 600),
                max_words=wc_config.get("max_words", 100),
                color_func=color_func
            )

            # 워드클라우드 생성
            wordcloud.generate_from_frequencies(processed_word_freq)
            self.logger.info("감정 기반 워드클라우드 생성 완료")

            # 이미지 저장
            if output_path and self.config["output"]["save_image"]:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                wordcloud.to_file(output_path)
                self.logger.info(f"워드클라우드 이미지 저장 완료: {output_path}")

            # 플롯 표시 (선택적)
            if self.config["output"]["show_plot"]:
                plt.figure(figsize=(10, 8))
                plt.imshow(wordcloud, interpolation='bilinear')
                plt.axis('off')
                plt.show()

            return True

        except Exception as e:
            self.logger.error(f"옵션 적용 감정 기반 워드클라우드 생성 실패: {e}")
            import traceback
            self.logger.error(f"오류 상세: {traceback.format_exc()}")
            return False

# 싱글톤 인스턴스 저장
_wordcloud_generator_instance = None

def generate_wordcloud(text: str, config_path: Optional[str] = None,
                      output_path: Optional[str] = None) -> bool:
    """
    편의 함수: 워드클라우드 생성

    Args:
        text: 워드클라우드 생성할 텍스트
        config_path: 설정 파일 경로 (None이면 기본 경로 사용)
        output_path: 이미지 저장 경로

    Returns:
        성공 여부
    """
    global _wordcloud_generator_instance
    if config_path is None:
        from src.config.settings import WORDCLOUD_CONFIG_PATH
        config_path = WORDCLOUD_CONFIG_PATH
    
    if _wordcloud_generator_instance is None:
        _wordcloud_generator_instance = WordCloudGenerator(config_path)
    return _wordcloud_generator_instance.generate(text, output_path)
