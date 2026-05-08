#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import pandas as pd
from typing import Dict, Any, Optional
from utils.logger import setup_logger, get_log_file_path, get_timestamp

class DataPreprocessing:
    """데이터 정제 모듈"""

    def __init__(self, config_path: str = "configs/preprocessing_config.json"):
        """
        데이터 정제기 초기화

        Args:
            config_path: 설정 파일 경로
        """
        self.config = self._load_config(config_path)
        self.timestamp = get_timestamp()

        # 로거 설정
        log_file = get_log_file_path(self.config["module_name"], self.timestamp)
        self.logger = setup_logger(self.config["module_name"], log_file)

        self.logger.info("데이터 정제기 초기화 완료")

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """설정 파일 로드"""
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {
                "module_name": "data_preprocessing",
                "output": {
                    "save_results": True
                }
            }

    def preprocess_by_user_id(self, input_file: str, user_id_column: int, output_dir: str) -> bool:
        """
        사용자 ID별로 데이터를 분리하여 저장

        Args:
            input_file: 입력 CSV 파일 경로
            user_id_column: 사용자 ID 열 인덱스 (0부터 시작)
            output_dir: 출력 디렉토리

        Returns:
            성공 여부
        """
        self.logger.info(f"데이터 정제 시작: {input_file}")

        try:
            # CSV 파일 읽기
            df = pd.read_csv(input_file)
            self.logger.info(f"데이터 로드 완료: {len(df)}행")

            # 사용자 ID별로 그룹화
            user_groups = df.groupby(df.iloc[:, user_id_column])

            # 출력 디렉토리 생성
            os.makedirs(output_dir, exist_ok=True)

            # 각 그룹을 별도 파일로 저장하고 원본에서 삭제
            processed_rows = 0
            for user_id, group in user_groups:
                output_file = os.path.join(output_dir, f"user_{user_id}.csv")
                group.to_csv(output_file, index=False)
                self.logger.info(f"사용자 {user_id} 데이터 저장: {len(group)}행 -> {output_file}")
                processed_rows += len(group)

            # 원본 파일에서 처리된 행들 삭제 (모든 그룹 처리 후)
            # 실제로는 메모리에 로드된 df에서 삭제
            remaining_df = df.drop(df.index[df.iloc[:, user_id_column].isin(user_groups.groups.keys())])
            remaining_df.to_csv(input_file, index=False)
            self.logger.info(f"원본 파일 업데이트: {len(remaining_df)}행 남음")

            self.logger.info(f"데이터 정제 완료: {len(user_groups)}개 사용자 그룹 생성")
            return True

        except Exception as e:
            self.logger.error(f"데이터 정제 실패: {e}")
            return False

def preprocess_data(input_file: str, user_id_column: int, output_dir: str,
                   config_path: str = "configs/preprocessing_config.json") -> bool:
    """
    편의 함수: 데이터 정제

    Args:
        input_file: 입력 CSV 파일 경로
        user_id_column: 사용자 ID 열 인덱스
        output_dir: 출력 디렉토리
        config_path: 설정 파일 경로

    Returns:
        성공 여부
    """
    preprocessor = DataPreprocessing(config_path)
    return preprocessor.preprocess_by_user_id(input_file, user_id_column, output_dir)
