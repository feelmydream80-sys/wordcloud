#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
메타데이터 통합 분석 모듈
"""

import os
import json
from datetime import datetime
from collections import Counter
from src.modules.leadership_analysis import LeadershipAnalysis

def calculate_consolidated_analysis(evaluations):
    """
    평가 리스트의 통합 분석 계산 - 단일 소스로 통일
    
    Args:
        evaluations (list): 평가 데이터 리스트
        
    Returns:
        dict: 통합 분석 결과
    """
    all_cleaned_texts = []
    all_emotion_words = {"positive": [], "negative": [], "neutral": []}
    all_nlp_words = []
    individual_leadership_results = []
    detected_profanities = []

    for evaluation in evaluations:
        # 정제된 텍스트 수집
        if 'preprocessing_results' in evaluation:
            all_cleaned_texts.append(evaluation['preprocessing_results']['cleaned_content'])
        elif 'evaluation_document' in evaluation:
            all_cleaned_texts.append(evaluation['evaluation_document'])
        
        # 감정 분석 결과 수집
        if 'emotion_analysis_results' in evaluation:
            emotion_result = evaluation['emotion_analysis_results']
            if 'analysis' in emotion_result and 'base_result' in emotion_result['analysis'] and 'mapped' in emotion_result['analysis']['base_result']:
                sentiment = emotion_result['analysis']['base_result']['mapped']['sentiment']
            elif 'fine_tuned_model' in emotion_result:
                sentiment = emotion_result['fine_tuned_model']['sentiment']
            elif 'base_model' in emotion_result:
                sentiment = emotion_result['base_model']['sentiment']
            else:
                sentiment = 'neutral'
            
            # 한국어 감정 라벨을 영어로 변환 (UTF-8 인코딩 문제 해결)
            if isinstance(sentiment, bytes):
                sentiment = sentiment.decode('utf-8')
            if sentiment == "긍정" or sentiment == "positive" or sentiment == "+":
                sentiment = "positive"
            elif sentiment == "부정" or sentiment == "negative" or sentiment == "-":
                sentiment = "negative"
            elif sentiment == "중립" or sentiment == "neutral" or sentiment == "0":
                sentiment = "neutral"
            
            # NLP 결과에서 meaningful words 추출
            if 'nlp_analysis_results' in evaluation:
                if 'analysis' in evaluation['nlp_analysis_results'] and 'meaningful_words' in evaluation['nlp_analysis_results']['analysis']:
                    meaningful_words = evaluation['nlp_analysis_results']['analysis']['meaningful_words']
                elif 'meaningful_words' in evaluation['nlp_analysis_results']:
                    meaningful_words = evaluation['nlp_analysis_results']['meaningful_words']
                else:
                    meaningful_words = []
                
                if sentiment == "positive":
                    all_emotion_words["positive"].extend(meaningful_words)
                elif sentiment == "negative":
                    all_emotion_words["negative"].extend(meaningful_words)
                else:
                    all_emotion_words["neutral"].extend(meaningful_words)
        
        # NLP 분석 결과 수집
        if 'nlp_analysis_results' in evaluation:
            if 'analysis' in evaluation['nlp_analysis_results'] and 'meaningful_words' in evaluation['nlp_analysis_results']['analysis']:
                all_nlp_words.extend(evaluation['nlp_analysis_results']['analysis']['meaningful_words'])
            elif 'meaningful_words' in evaluation['nlp_analysis_results']:
                all_nlp_words.extend(evaluation['nlp_analysis_results']['meaningful_words'])
        
        # 리더십 분석 결과 수집
        if 'leadership_analysis_results' in evaluation:
            individual_leadership_results.append(evaluation['leadership_analysis_results'])
        
        # 욕설 분석 결과 수집
        if 'profanity_analysis_results' in evaluation:
            if 'detected_profanity' in evaluation['profanity_analysis_results']:
                detected_profanities.extend(evaluation['profanity_analysis_results']['detected_profanity'])
    
    # 통합 감정 분석 - 가중 평균 기반 신뢰도 계산
    weighted_positive = 0.0
    weighted_negative = 0.0
    weighted_neutral = 0.0
    total_weight = 0.0
    
    for evaluation in evaluations:
        if 'emotion_analysis_results' in evaluation:
            emotion_result = evaluation['emotion_analysis_results']
            if 'analysis' in emotion_result and 'base_result' in emotion_result['analysis'] and 'mapped' in emotion_result['analysis']['base_result']:
                if 'sentiment_scores' in emotion_result['analysis']['base_result']['mapped']:
                    scores = emotion_result['analysis']['base_result']['mapped']['sentiment_scores']
                    confidence = emotion_result['analysis']['base_result']['mapped'].get('confidence', 0.5)
                    
                    weighted_positive += scores.get('positive', 0.0) * confidence
                    weighted_negative += scores.get('negative', 0.0) * confidence
                    weighted_neutral += scores.get('neutral', 0.0) * confidence
                    total_weight += confidence
            elif 'base_model' in emotion_result and 'sentiment_scores' in emotion_result['base_model']:
                scores = emotion_result['base_model']['sentiment_scores']
                confidence = emotion_result['base_model'].get('confidence', 0.5)
                
                weighted_positive += scores.get('positive', 0.0) * confidence
                weighted_negative += scores.get('negative', 0.0) * confidence
                weighted_neutral += scores.get('neutral', 0.0) * confidence
                total_weight += confidence
            elif 'fine_tuned_model' in emotion_result and 'sentiment_scores' in emotion_result['fine_tuned_model']:
                scores = emotion_result['fine_tuned_model']['sentiment_scores']
                confidence = emotion_result['fine_tuned_model'].get('confidence', 0.5)
                
                weighted_positive += scores.get('positive', 0.0) * confidence
                weighted_negative += scores.get('negative', 0.0) * confidence
                weighted_neutral += scores.get('neutral', 0.0) * confidence
                total_weight += confidence
    
    # 가중 평균 확률 계산
    if total_weight > 0:
        avg_positive = weighted_positive / total_weight
        avg_negative = weighted_negative / total_weight
        avg_neutral = weighted_neutral / total_weight
    else:
        avg_positive = 0.0
        avg_negative = 0.0
        avg_neutral = 0.0
    
    # 최종 감정 결정
    consolidated_sentiment = "neutral"
    if avg_positive > avg_negative and avg_positive > avg_neutral:
        consolidated_sentiment = "positive"
    elif avg_negative > avg_positive and avg_negative > avg_neutral:
        consolidated_sentiment = "negative"
    
    # 신뢰도 계산 - 최종 감정에 해당하는 가중 평균 확률
    if consolidated_sentiment == "positive":
        confidence_score = avg_positive
    elif consolidated_sentiment == "negative":
        confidence_score = avg_negative
    else:
        confidence_score = avg_neutral
    
    # 단어 빈도 계산
    word_freq = dict(Counter(all_nlp_words))

    # 욕설 통계 계산
    all_profanity_words = []
    total_profanity_count = 0
    evaluations_with_profanity = 0

    for evaluation in evaluations:
        profanity_results = evaluation.get("profanity_analysis_results", {})
        profanity_count = profanity_results.get("profanity_count", 0)
        detected_profanity = profanity_results.get("detected_profanity", [])

        # 'legacy:' prefix 제거하고 실제 비속어만 저장
        clean_profanity = []
        for word in detected_profanity:
            if word.startswith('legacy:'):
                clean_profanity.append(word.replace('legacy:', ''))
            elif word != 'korcen_detected':  # korcen_detected는 구체적 단어가 아니므로 제외
                clean_profanity.append(word)

        total_profanity_count += profanity_count
        all_profanity_words.extend(clean_profanity)

        if profanity_count > 0:
            evaluations_with_profanity += 1

    profanity_freq = dict(Counter(all_profanity_words))

    # 리더십 통합 분석
    leadership_analyzer = LeadershipAnalysis()
    leadership_consolidated = leadership_analyzer.consolidate_leadership_analysis(individual_leadership_results)

    # combined_text 계산
    combined_text = ' '.join(all_cleaned_texts)
    
    # evaluator_analysis 계산
    department_distribution = {}
    position_distribution = {}
    hierarchy_level_distribution = {}
    for evaluation in evaluations:
        if 'evaluator_department' in evaluation:
            dept = evaluation['evaluator_department']
            department_distribution[dept] = department_distribution.get(dept, 0) + 1
        if 'evaluator_position' in evaluation:
            pos = evaluation['evaluator_position']
            position_distribution[pos] = position_distribution.get(pos, 0) + 1
        if 'evaluator_hierarchy_level' in evaluation:
            level = evaluation['evaluator_hierarchy_level']
            hierarchy_level_distribution[level] = hierarchy_level_distribution.get(level, 0) + 1
    
    return {
        "combined_cleaned_content": combined_text,
        "overall_sentiment": consolidated_sentiment,
        "confidence_score": round(confidence_score, 3),
        "consolidated_emotion_words": {k: list(set(v)) for k, v in all_emotion_words.items()},
        "consolidated_nlp_words": list(set(all_nlp_words)),
        "word_frequency": word_freq,
        "evaluator_analysis": {
            "department_distribution": department_distribution,
            "position_distribution": position_distribution,
            "hierarchy_level_distribution": hierarchy_level_distribution
        },
        "profanity_consolidated": {
            "total_profanity_count": total_profanity_count,
            "profanity_words": list(set(all_profanity_words)),
            "profanity_frequency": profanity_freq,
            "evaluations_with_profanity": evaluations_with_profanity,
            "profanity_ratio": evaluations_with_profanity / len(evaluations) if evaluations else 0
        },
        "leadership_consolidated": leadership_consolidated
    }
