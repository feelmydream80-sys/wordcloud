"""Analysis service - handles text analysis operations."""

import os
import json
import uuid
from datetime import datetime
from src.config.settings import (
    NLP_CONFIG_PATH,
    WORDCLOUD_CONFIG_PATH,
    OUTPUTS_DIR_PATH
)
from src.modules.nlp_analysis import analyze_text
from src.modules.wordcloud_generator import WordCloudGenerator
from src.modules.sarcasm_analysis import analyze_sarcasm
from src.modules.emotion_analysis import analyze_emotion


def analyze_text(data):
    """Analyze text for emotion and sarcasm."""
    try:
        sentences = data.get('sentences', '').strip().split('\n')
        sentences = [s.strip() for s in sentences if s.strip()]
        wordcloud_pos = data.get('wordcloud_pos', ["Noun", "Verb", "Adjective"])

        results = []
        total_pos = 0.0
        total_neg = 0.0
        all_text = ' '.join(sentences)

        for sentence in sentences:
            emotion_result = analyze_emotion(sentence)
            sarcasm_result = analyze_sarcasm(sentence)

            extracted = []
            pos_score = 0.0
            neg_score = 0.0
            sarcasm_score = 0.0

            if "analysis" in emotion_result:
                analysis = emotion_result["analysis"]

                if "base_result" in analysis and "mapped" in analysis["base_result"]:
                    base_result = analysis["base_result"]["mapped"]
                    if "sentiment_scores" in base_result:
                        pos_score = base_result["sentiment_scores"].get("positive", 0.0)
                        neg_score = base_result["sentiment_scores"].get("negative", 0.0)

                    if "top_3" in base_result:
                        for pred in base_result["top_3"]:
                            extracted.append(f"{pred['label']}({pred['confidence']:.3f})")

            if "analysis" in sarcasm_result:
                analysis = sarcasm_result["analysis"]

                if "fine_tuned_result" in analysis and "mapped" in analysis["fine_tuned_result"]:
                    fine_tuned_result = analysis["fine_tuned_result"]["mapped"]
                    if fine_tuned_result["label"] == "Sarcasm":
                        sarcasm_score = fine_tuned_result["confidence"]
                elif "sklearn_result" in analysis and "mapped" in analysis["sklearn_result"]:
                    sklearn_result = analysis["sklearn_result"]["mapped"]
                    if sklearn_result["label"] == "Sarcasm":
                        sarcasm_score = sklearn_result["confidence"]

            if sarcasm_score == 0.0 and not any(key in sarcasm_result.get("analysis", {}) for key in ["fine_tuned_result", "sklearn_result"]):
                sarcasm_score = 0.0

            total_pos += pos_score
            total_neg += neg_score

            results.append({
                'sentence': sentence,
                'extracted': ', '.join(extracted),
                'positive_score': round(pos_score, 3),
                'negative_score': round(neg_score, 3),
                'sarcasm_score': round(sarcasm_score, 3)
            })

        if all_text.strip():
            from src.modules.nlp_analysis import analyze_text as nlp_analyze_text
            nlp_result = nlp_analyze_text(all_text, config_path=NLP_CONFIG_PATH)
            meaningful_words = []
            if 'analysis' in nlp_result and 'okt' in nlp_result['analysis']:
                okt_result = nlp_result['analysis']['okt']
                meaningful_words = okt_result.get('meaningful_words', [])

            from collections import Counter
            word_freq = dict(Counter(meaningful_words))

            word_scores = {}
            for sentence in sentences:
                emotion_result = analyze_emotion(sentence)

                score = 0.0
                if "analysis" in emotion_result:
                    analysis = emotion_result["analysis"]

                    if "base_result" in analysis and "mapped" in analysis["base_result"]:
                        base_result = analysis["base_result"]["mapped"]
                        if base_result["sentiment"] == "positive":
                            score = 1.0
                        elif base_result["sentiment"] == "negative":
                            score = -1.0
                        else:
                            score = 0.0

                nlp_result = nlp_analyze_text(sentence, config_path=NLP_CONFIG_PATH)
                sentence_words = []
                if 'analysis' in nlp_result and 'okt' in nlp_result['analysis']:
                    okt_result = nlp_result['analysis']['okt']
                    sentence_words = okt_result.get('meaningful_words', [])

                for word in sentence_words:
                    word_scores[word] = score

            generator = WordCloudGenerator(config_path=WORDCLOUD_CONFIG_PATH)
            output_path = os.path.abspath(os.path.join(OUTPUTS_DIR_PATH, f"wordcloud_{int(datetime.now().timestamp() * 1000)}.png"))
            success = generator.generate_with_colors(word_freq, word_scores, output_path)

            if success:
                results.append({'wordcloud_url': f"/api/wordcloud/outputs/{os.path.basename(output_path)}"})
            else:
                results.append({'wordcloud_url': None})

        return results

    except Exception as e:
        return {'success': False, 'error': str(e)}, 500


def analyze_sarcasm(data):
    """Analyze text for sarcasm."""
    try:
        sentences = data.get('sentences', '').strip().split('\n')
        sentences = [s.strip() for s in sentences if s.strip()]

        results = []

        for sentence in sentences:
            try:
                from src.modules.sarcasm_analysis import SarcasmAnalysis
                analyzer = SarcasmAnalysis(config_path="wordcloud_project/configs/sarcasm_config.json")
                analysis_result = analyzer.analyze(sentence)
                if 'analysis' in analysis_result and 'fine_tuned_result' in analysis_result['analysis']:
                    result = analysis_result['analysis']['fine_tuned_result']
                    if 'mapped' in result:
                        label = result['mapped']['label']
                        confidence = result['mapped']['confidence']
                        results.append({
                            'sentence': sentence,
                            'label': label,
                            'confidence': round(confidence, 3)
                        })
                    else:
                        results.append({
                            'sentence': sentence,
                            'label': '분석 실패',
                            'confidence': 0.0
                        })
                else:
                    results.append({
                        'sentence': sentence,
                        'label': '분석 실패',
                        'confidence': 0.0
                    })
            except Exception as e:
                results.append({
                    'sentence': sentence,
                    'label': f'오류: {str(e)}',
                    'confidence': 0.0
                })

        return results

    except Exception as e:
        return {'success': False, 'error': str(e)}, 500
