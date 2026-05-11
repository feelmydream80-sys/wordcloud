"""Perspective analysis service - generic column-based grouping engine."""
import os
import json
from collections import Counter
from datetime import datetime
from src.config.settings import OUTPUTS_DIR_PATH, WORDCLOUD_CONFIG_PATH
from src.modules.wordcloud_generator import WordCloudGenerator


# Column types that are NOT groupable (free-text, generated IDs, etc.)
SKIP_COLUMNS = {
    'evaluation_id', 'session_id', 'evaluator_id',
    'evaluation_document', 'evaluation_document_original',
    'version', 'data_integrity_hash',
    'target_employee_id',
    'evaluator_hierarchy_level', 'target_hierarchy_level',
}


def load_batch_summary(batch_path):
    """Load batch_summary.json directly (all employee metadata embedded)."""
    summary_path = os.path.join(batch_path, "tmeta", "batch_summary.json")
    if not os.path.exists(summary_path):
        return None
    with open(summary_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _build_column_label_map(batch_summary):
    """Build field_name → display_label mapping from batch's column mappings.

    Uses processing_config.mappings CSV column names as display labels.
    Falls back to readable field name if mapping unavailable.
    """
    label_map = {}

    mappings = (
        batch_summary
        .get('processing_config', {})
        .get('mappings', {})
    )
    for field, csv_col in mappings.items():
        if isinstance(csv_col, str) and csv_col.strip():
            label_map[field] = csv_col.strip()

    return label_map


def _field_to_label(field_name):
    """Convert internal field name to readable Korean label as fallback."""
    KNOWN_LABELS = {
        'evaluator_position': '평가자 직책',
        'evaluator_department': '평가자 부서',
        'evaluation_date': '평가 실시 일',
        'target_employee_department': '대상자 부서',
        'target_employee_position': '대상자 직책',
        'preprocessing_results': '전처리 결과',
    }
    return KNOWN_LABELS.get(field_name, field_name.replace('_', ' '))


def get_groupable_columns(batch_summary):
    """Discover which evaluation fields can be used as group-by columns.

    Scans all evaluations in the batch and returns field names that:
    - Are string type
    - Have at most 50 unique values (categorical, not free-text)
    - Are not in SKIP_COLUMNS
    - Appear in at least one evaluation
    """
    label_map = _build_column_label_map(batch_summary)
    value_sets = {}
    field_sample = {}

    for er in batch_summary.get('employee_results', []):
        meta = er.get('metadata', {})
        for ev in meta.get('evaluations', []):
            for key, val in ev.items():
                if key in SKIP_COLUMNS:
                    continue
                if isinstance(val, str) and val.strip():
                    if key not in value_sets:
                        value_sets[key] = set()
                        field_sample[key] = val
                    value_sets[key].add(val)

    columns = []
    for key, values in value_sets.items():
        if 1 < len(values) <= 50:
            columns.append({
                'field': key,
                'label': label_map.get(key, _field_to_label(key)),
                'unique_count': len(values),
                'sample_values': sorted(values)[:5],
                'sample_value': field_sample.get(key, ''),
            })

    columns.sort(key=lambda c: -c['unique_count'])
    return columns


def get_employee_list(batch_summary):
    """Get list of employees in batch.

    Returns:
        list of dict: [{employee_id, department, position, evaluation_count}, ...]
    """
    employees = []
    for er in batch_summary.get('employee_results', []):
        meta = er.get('metadata', {})
        employees.append({
            'employee_id': meta.get('target_employee_id'),
            'department': meta.get('target_employee_department'),
            'position': meta.get('target_employee_position'),
            'evaluation_count': meta.get('total_evaluations', 0),
        })
    employees.sort(key=lambda e: e['employee_id'] or '')
    return employees


def get_column_values(batch_summary, column_name, employee_id=None):
    """Get unique values + evaluation count for a specific column.

    When employee_id is given, only that employee's evaluations are scanned.
    Otherwise scans all employees.

    Returns list sorted by count descending.
    """
    value_counts = Counter()

    for er in batch_summary.get('employee_results', []):
        meta = er.get('metadata', {})
        emp_id = meta.get('target_employee_id')

        if employee_id and emp_id != employee_id:
            continue

        for ev in meta.get('evaluations', []):
            val = ev.get(column_name)
            if isinstance(val, str) and val.strip():
                value_counts[val] += 1

    return [
        {'value': v, 'count': c}
        for v, c in value_counts.most_common()
    ]


def filter_evaluations(batch_summary, column_name, column_value, employee_id=None):
    """Filter evaluations across all employees by column == value.

    Args:
        batch_summary: Loaded batch_summary.json dict
        column_name: Evaluation field to filter on (e.g. 'evaluator_position')
        column_value: Value to match (e.g. '과장')
        employee_id: Optional - filter to a single employee

    Returns:
        list of dict: [{evaluation, employee_id, employee_department,
                        employee_position, ...}, ...]
    """
    results = []

    for er in batch_summary.get('employee_results', []):
        meta = er.get('metadata', {})
        emp_id = meta.get('target_employee_id')

        if employee_id and emp_id != employee_id:
            continue

        for ev in meta.get('evaluations', []):
            ev_val = ev.get(column_name)
            if ev_val == column_value:
                results.append({
                    'evaluation': ev,
                    'employee_id': emp_id,
                    'employee_department': meta.get('target_employee_department'),
                    'employee_position': meta.get('target_employee_position'),
                })

    return results


def extract_words(filtered_evaluations, wordcloud_pos=None, remove_profanity=False):
    """Extract and count words from filtered evaluations.

    Args:
        filtered_evaluations: Output of filter_evaluations()
        wordcloud_pos: POS types to include (e.g. ['Noun', 'Verb'])
                       None = use all meaningful_words without POS filtering
        remove_profanity: Remove profanity words

    Returns:
        dict: {word_frequency: {word: count, ...},
               total_evaluations: N,
               total_employees: N,
               profanity_words: [list of removed words]}
    """
    if wordcloud_pos is None:
        wordcloud_pos = ['Noun']

    all_words = []
    profanity_set = set()
    employee_ids = set()

    for item in filtered_evaluations:
        ev = item['evaluation']
        employee_ids.add(item['employee_id'])

        nlp = ev.get('nlp_analysis_results', {})

        # Extract meaningful words with POS info
        pos_data = None
        if isinstance(nlp, dict):
            analysis = nlp.get('analysis', {})
            if isinstance(analysis, dict):
                pos_data = analysis.get('meaningful_words_with_pos')

        if pos_data and isinstance(pos_data, list):
            for entry in pos_data:
                if isinstance(entry, list) and len(entry) == 2:
                    word, pos = entry
                    if pos in wordcloud_pos:
                        all_words.append(word)
                elif isinstance(entry, str):
                    all_words.append(entry)
        else:
            # Fallback: use meaningful_words list
            meaningful = None
            if isinstance(nlp, dict):
                analysis = nlp.get('analysis', {})
                if isinstance(analysis, dict):
                    meaningful = analysis.get('meaningful_words')
                if not meaningful:
                    meaningful = nlp.get('meaningful_words')
            if meaningful and isinstance(meaningful, list):
                all_words.extend(meaningful)

        # Collect profanity
        if remove_profanity:
            prof = ev.get('profanity_analysis_results', {})
            if isinstance(prof, dict):
                detected = prof.get('detected_profanity', [])
                if isinstance(detected, list):
                    profanity_set.update(detected)

    word_freq = dict(Counter(all_words))

    if remove_profanity and profanity_set:
        for pw in profanity_set:
            pw_clean = pw.replace('legacy:', '')
            if pw_clean in word_freq:
                del word_freq[pw_clean]

    return {
        'word_frequency': word_freq,
        'total_evaluations': len(filtered_evaluations),
        'total_employees': len(employee_ids),
        'profanity_removed': list(profanity_set) if remove_profanity else [],
    }


def calculate_word_scores(filtered_evaluations, word_frequency):
    """Calculate sentiment scores per word based on emotion analysis.

    For each word, finds all filtered evaluations containing that word and
    averages their sentiment scores. Score > 0 = positive, < 0 = negative.

    Args:
        filtered_evaluations: Output of filter_evaluations()
        word_frequency: {word: count, ...}

    Returns:
        dict: {word: score, ...}
    """
    word_scores = {}

    for word in word_frequency.keys():
        total_score = 0.0
        count = 0

        for item in filtered_evaluations:
            ev = item['evaluation']

            # Check if word is in this evaluation's meaningful words
            nlp = ev.get('nlp_analysis_results', {})
            meaningful_words = []
            if isinstance(nlp, dict):
                analysis = nlp.get('analysis', {})
                if isinstance(analysis, dict):
                    meaningful_words = analysis.get('meaningful_words', [])
                if not meaningful_words:
                    meaningful_words = nlp.get('meaningful_words', [])

            if word not in meaningful_words:
                continue

            # Get sentiment scores
            emotion = ev.get('emotion_analysis_results', {})
            pos_score = 0.0
            neg_score = 0.0

            if isinstance(emotion, dict):
                analysis = emotion.get('analysis', {})
                if isinstance(analysis, dict):
                    base_result = analysis.get('base_result', {})
                    if isinstance(base_result, dict):
                        mapped = base_result.get('mapped', {})
                        if isinstance(mapped, dict):
                            scores = mapped.get('sentiment_scores', {})
                            if isinstance(scores, dict):
                                pos_score = scores.get('positive', 0.0) or 0.0
                                neg_score = scores.get('negative', 0.0) or 0.0

                if pos_score == 0.0 and neg_score == 0.0:
                    base_model = emotion.get('base_model', {})
                    if isinstance(base_model, dict):
                        scores = base_model.get('sentiment_scores', {})
                        if isinstance(scores, dict):
                            pos_score = scores.get('positive', 0.0) or 0.0
                            neg_score = scores.get('negative', 0.0) or 0.0

            score = (pos_score - neg_score) * 2.5
            total_score += score
            count += 1

        word_scores[word] = round(total_score / count, 4) if count > 0 else 0.0

    return word_scores


def _save_and_return_wordcloud(word_freq, word_scores, options, filename_prefix):
    """Generate wordcloud PNG and return URL + info."""
    generator = WordCloudGenerator(config_path=WORDCLOUD_CONFIG_PATH)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{filename_prefix}_{timestamp}.png"
    output_path = os.path.abspath(os.path.join(OUTPUTS_DIR_PATH, filename))

    success = generator.generate_with_colors_and_options(
        word_freq, word_scores, output_path,
        background_color=options.get('background_color', 'white'),
        max_words=options.get('max_words', 100),
        width=options.get('width', 800),
        height=options.get('height', 600),
    )

    if not success:
        return None

    return {
        'wordcloud_url': f"/api/wordcloud/outputs/{filename}",
        'wordcloud_info': {
            'word_frequency': word_freq,
            'word_scores': word_scores,
            'total_words': len(word_freq),
            'morphology_types': options.get('wordcloud_pos', ['Noun']),
            'generation_timestamp': datetime.now().isoformat() + 'Z',
        }
    }


def generate_group_wordcloud(batch_path, employee_id, column_name, column_value, options):
    """Generate wordcloud for ONE employee, filtered by column_name == column_value.

    Args:
        batch_path: Path to batch directory
        employee_id: Target employee ID (required, single employee only)
        column_name: Evaluation field to filter on (e.g. 'evaluator_position')
        column_value: Value to match (e.g. '과장')
        options: dict with wordcloud_pos, background_color, etc.

    Returns:
        dict with wordcloud_url, wordcloud_info, stats, or None
    """
    if not employee_id:
        return None

    batch_summary = load_batch_summary(batch_path)
    if not batch_summary:
        return None

    filtered = filter_evaluations(batch_summary, column_name, column_value, employee_id)

    if len(filtered) == 0:
        return None

    word_data = extract_words(
        filtered,
        wordcloud_pos=options.get('wordcloud_pos', ['Noun']),
        remove_profanity=options.get('remove_profanity', False),
    )

    wf = word_data['word_frequency']
    if not wf:
        return None

    # Calculate average sentiment
    pos_sum = neg_sum = 0.0
    for item in filtered:
        ev = item['evaluation']
        emotion = ev.get('emotion_analysis_results', {})
        scores = {}
        if isinstance(emotion, dict):
            analysis = emotion.get('analysis', {})
            if isinstance(analysis, dict):
                br = analysis.get('base_result', {})
                if isinstance(br, dict):
                    mp = br.get('mapped', {})
                    if isinstance(mp, dict):
                        scores = mp.get('sentiment_scores', {})

        if not isinstance(scores, dict):
            scores = {}
        pos_sum += scores.get('positive', 0.0) or 0.0
        neg_sum += scores.get('negative', 0.0) or 0.0

    n = len(filtered)
    word_scores = calculate_word_scores(filtered, wf)
    result = _save_and_return_wordcloud(
        wf, word_scores, options,
        f"group_{column_name}_{column_value}"
    )

    if not result:
        return None

    # Determine display label
    label_map = _build_column_label_map(batch_summary)
    column_label = label_map.get(column_name, _field_to_label(column_name))

    result['wordcloud_info']['stats'] = {
        'total_evaluations': word_data['total_evaluations'],
        'total_employees': word_data['total_employees'],
        'column_name': column_name,
        'column_label': column_label,
        'column_value': column_value,
        'average_sentiment': {
            'positive': round(pos_sum / n, 4) if n > 0 else 0,
            'negative': round(neg_sum / n, 4) if n > 0 else 0,
        }
    }

    return result


def generate_all_group_wordclouds(batch_path, employee_id, column_name, options):
    """Generate wordclouds for ALL distinct values in a column, for ONE employee.

    Uses ThreadPoolExecutor for parallel generation.

    Args:
        batch_path: Path to batch directory
        employee_id: Target employee ID (required)
        column_name: Evaluation field to group by

    Returns:
        dict: {value: {wordcloud_url, evaluation_count, ...}, ...}
    """
    if not employee_id:
        return None

    batch_summary = load_batch_summary(batch_path)
    if not batch_summary:
        return None

    values = get_column_values(batch_summary, column_name, employee_id)
    results = {}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import multiprocessing

    def process_value(v):
        item = v
        opts = dict(options)
        result = generate_group_wordcloud(batch_path, employee_id, column_name, item['value'], opts)
        if result:
            return {
                'value': item['value'],
                'wordcloud_url': result['wordcloud_url'],
                'evaluation_count': item['count'],
                'wordcloud_info': result['wordcloud_info'],
            }
        else:
            return {
                'value': item['value'],
                'wordcloud_url': None,
                'evaluation_count': item['count'],
                'warning': f"워드클라우드 생성 실패 (평가 {item['count']}개)",
            }

    num_workers = min(multiprocessing.cpu_count(), 4)
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_value, v): v for v in values}
        for future in as_completed(futures):
            r = future.result()
            results[r['value']] = {
                'wordcloud_url': r['wordcloud_url'],
                'evaluation_count': r['evaluation_count'],
                'warning': r.get('warning'),
                'wordcloud_info': r.get('wordcloud_info'),
            }

    return results
