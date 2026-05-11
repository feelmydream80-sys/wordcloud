"""Perspective analysis service - generic multi-filter grouping engine."""
import os
import json
import re
from collections import Counter
from datetime import datetime
from src.config.settings import OUTPUTS_DIR_PATH, WORDCLOUD_CONFIG_PATH
from src.modules.wordcloud_generator import WordCloudGenerator


SKIP_COLUMNS = {
    'evaluation_id', 'session_id', 'evaluator_id',
    'evaluation_document', 'evaluation_document_original',
    'version', 'data_integrity_hash',
    'target_employee_id',
    'evaluator_hierarchy_level', 'target_hierarchy_level',
}


def load_batch_summary(batch_path):
    summary_path = os.path.join(batch_path, "tmeta", "batch_summary.json")
    if not os.path.exists(summary_path):
        return None
    with open(summary_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _build_column_label_map(batch_summary):
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
    KNOWN_LABELS = {
        'evaluator_position': '평가자 직책',
        'evaluator_department': '평가자 부서',
        'evaluation_date': '평가 실시 일',
        'evaluation_date__year': '평가 연도',
        'evaluation_date__month': '평가 월',
        'target_employee_department': '대상자 부서',
        'target_employee_position': '대상자 직책',
        'preprocessing_results': '전처리 결과',
    }
    return KNOWN_LABELS.get(field_name, field_name.replace('_', ' '))


def _get_eval_field_value(ev, raw_field):
    """Extract value from evaluation for a possibly-suffixed field name.

    Supports:
      'evaluator_position'     → ev['evaluator_position']
      'evaluation_date__year'  → year from ev['evaluation_date']
      'evaluation_date__month' → month from ev['evaluation_date']
    """
    parts = raw_field.split('__', 1)
    base_field = parts[0]
    modifier = parts[1] if len(parts) > 1 else None

    raw_val = ev.get(base_field)
    if raw_val is None:
        return None

    if modifier == 'year':
        if isinstance(raw_val, str) and len(raw_val) >= 4:
                return raw_val[:4]
        return None
    elif modifier == 'month':
        if isinstance(raw_val, str) and len(raw_val) >= 7:
            parts = raw_val.split('-')
            if len(parts) >= 2:
                return parts[1]
        return None

    return raw_val


def _resolve_field_name(raw_field):
    """Return the actual evaluation dict key for a possibly-suffixed field."""
    return raw_field.split('__')[0]


def get_groupable_columns(batch_summary):
    """Discover groupable columns, including synthetic date modifiers."""
    label_map = _build_column_label_map(batch_summary)
    value_sets = {}
    field_sample = {}
    has_date = False

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
                    if key == 'evaluation_date':
                        has_date = True

    columns = []
    for key, values in value_sets.items():
        if 1 < len(values) <= 50:
            columns.append({
                'field': key,
                'label': label_map.get(key, _field_to_label(key)),
                'unique_count': len(values),
                'sample_values': sorted(values)[:5],
                'type': 'direct',
            })

    # Add synthetic date modifiers if evaluation_date exists
    if has_date:
        year_set = set()
        month_set = set()
        for er in batch_summary.get('employee_results', []):
            for ev in er.get('metadata', {}).get('evaluations', []):
                raw = ev.get('evaluation_date', '')
                if isinstance(raw, str) and len(raw) >= 4:
                    year_set.add(raw[:4])
                if isinstance(raw, str) and len(raw) >= 7:
                    parts = raw.split('-')
                    if len(parts) >= 2:
                        month_set.add(parts[1])
        if len(year_set) > 1:
            columns.append({
                'field': 'evaluation_date__year',
                'label': '평가 연도',
                'unique_count': len(year_set),
                'sample_values': sorted(year_set),
                'type': 'synthetic',
            })
        if len(month_set) > 1:
            columns.append({
                'field': 'evaluation_date__month',
                'label': '평가 월',
                'unique_count': len(month_set),
                'sample_values': sorted(month_set),
                'type': 'synthetic',
            })
        # Add date itself as a column (already collected above)

    columns.sort(key=lambda c: -c['unique_count'])
    return columns


def get_employee_list(batch_summary):
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


def get_column_values(batch_summary, raw_field, employee_id=None):
    """Get unique values for a field, supporting __year/__month suffixes."""
    base_field = _resolve_field_name(raw_field)
    value_counts = Counter()

    for er in batch_summary.get('employee_results', []):
        meta = er.get('metadata', {})
        emp_id = meta.get('target_employee_id')
        if employee_id and emp_id != employee_id:
            continue
        for ev in meta.get('evaluations', []):
            val = _get_eval_field_value(ev, raw_field)
            if isinstance(val, str) and val.strip():
                value_counts[val] += 1

    return [
        {'value': v, 'count': c}
        for v, c in value_counts.most_common()
    ]


def filter_evaluations(batch_summary, filters, employee_id=None):
    """Filter evaluations with per-filter AND/OR connectors.

    Precedence: consecutive 'or' filters form a group (OR'd together),
    then groups are AND'd together.

    Example:
        [A, {or: B}, {or: C}, {and: D}, {or: E}]
        → (A OR B OR C) AND (D OR E)

    Args:
        batch_summary: Loaded batch_summary.json dict
        filters: list of dicts
            [
                {"column": "evaluator_position", "value": "과장"},          # first: group start
                {"connector": "or",  "column": "evaluation_date", "value": "2026-01-19"},  # joins prev group
                {"connector": "or",  "column": "evaluation_date", "value": "2026-01-21"},  # joins prev group
                {"connector": "and", "column": "evaluator_department", "value": "생산부"},   # new group
            ]
            → (position=과장 OR date=1/19 OR date=1/21) AND (department=생산부)
        employee_id: Optional - restrict to one employee

    Returns:
        list of dict
    """
    if not filters:
        return []

    results = []
    for er in batch_summary.get('employee_results', []):
        meta = er.get('metadata', {})
        emp_id = meta.get('target_employee_id')
        if employee_id and emp_id != employee_id:
            continue

        for ev in meta.get('evaluations', []):
            # Step 1: evaluate each filter independently
            conds = []
            for f in filters:
                col = f.get('column', f.get('column_name'))
                val = f.get('value', f.get('column_value'))
                ev_val = _get_eval_field_value(ev, col)
                conds.append(ev_val == val)

            if not conds:
                continue

            # Step 2: group by connectors
            # consecutive 'or' filters share a group (OR'd)
            # 'and' filters start a new group
            # groups are AND'd together
            groups = [[0]]
            for i in range(1, len(conds)):
                connector = filters[i].get('connector', 'and')
                if connector == 'or':
                    groups[-1].append(i)
                else:
                    groups.append([i])

            # Step 3: OR within group, AND between groups
            group_results = [any(conds[j] for j in g) for g in groups]
            combined = all(group_results)

            if combined:
                results.append({
                    'evaluation': ev,
                    'employee_id': emp_id,
                    'employee_department': meta.get('target_employee_department'),
                    'employee_position': meta.get('target_employee_position'),
                })

    return results


def extract_words(filtered_evaluations, wordcloud_pos=None, remove_profanity=False):
    if wordcloud_pos is None:
        wordcloud_pos = ['Noun']

    all_words = []
    profanity_set = set()
    employee_ids = set()

    for item in filtered_evaluations:
        ev = item['evaluation']
        employee_ids.add(item['employee_id'])

        nlp = ev.get('nlp_analysis_results', {})
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
            meaningful = None
            if isinstance(nlp, dict):
                analysis = nlp.get('analysis', {})
                if isinstance(analysis, dict):
                    meaningful = analysis.get('meaningful_words')
                if not meaningful:
                    meaningful = nlp.get('meaningful_words')
            if meaningful and isinstance(meaningful, list):
                all_words.extend(meaningful)

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
    word_scores = {}
    for word in word_frequency.keys():
        total_score = 0.0
        count = 0
        for item in filtered_evaluations:
            ev = item['evaluation']
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


def _filters_to_desc(filters):
    """Convert filters list to a compact string for filename."""
    parts = []
    for f in filters:
        col = f.get('column', '')
        val = f.get('value', '')
        col_short = col.replace('evaluation_date', 'date') \
                        .replace('evaluator_', '') \
                        .replace('__', '_')
        parts.append(f"{col_short}_{val}")
    return '_'.join(parts) if parts else 'all'


def generate_group_wordcloud(batch_path, employee_id, filters, options):
    """Generate wordcloud for ONE employee with multi-filter conditions.

    Args:
        batch_path: Path to batch directory
        employee_id: Target employee ID (required)
        filters: list of dicts [{"column": "...", "value": "..."}, ...]
        options: dict with wordcloud_pos, background_color, etc.

    Returns:
        dict or None
    """
    if not employee_id or not filters:
        return None

    batch_summary = load_batch_summary(batch_path)
    if not batch_summary:
        return None

    filtered = filter_evaluations(batch_summary, filters, employee_id)
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

    # Average sentiment
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
    result = _save_and_return_wordcloud(wf, word_scores, options, _filters_to_desc(filters))
    if not result:
        return None

    # Determine display labels
    label_map = _build_column_label_map(batch_summary)
    filter_labels = []
    for f in filters:
        col = f.get('column', '')
        val = f.get('value', '')
        lbl = label_map.get(col, _field_to_label(col))
        filter_labels.append(f"{lbl}={val}")

    result['wordcloud_info']['stats'] = {
        'total_evaluations': word_data['total_evaluations'],
        'total_employees': word_data['total_employees'],
        'filters': filters,
        'filter_display': ', '.join(filter_labels),
        'average_sentiment': {
            'positive': round(pos_sum / n, 4) if n > 0 else 0,
            'negative': round(neg_sum / n, 4) if n > 0 else 0,
        }
    }
    return result


def generate_all_group_wordclouds(batch_path, employee_id, group_column, prefilters, options):
    """Generate wordclouds for ALL distinct values in group_column.

    Pre-filters (prefilters) are applied first, then results are grouped by
    each distinct value in group_column.

    Args:
        batch_path: Path to batch directory
        employee_id: Target employee ID
        group_column: Column whose distinct values become groups
        prefilters: Base filters applied before grouping (e.g. [{"column":"evaluation_date__year","value":"2026"}])
        options: Wordcloud options

    Returns:
        dict: {value: {wordcloud_url, evaluation_count, ...}, ...}
    """
    if not employee_id or not group_column:
        return None

    batch_summary = load_batch_summary(batch_path)
    if not batch_summary:
        return None

    group_values = get_column_values(batch_summary, group_column, employee_id)
    results = {}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    import multiprocessing

    def process_value(v):
        # Build filters: prefilters + current group value
        filters = list(prefilters)
        filters.append({'column': group_column, 'value': v['value']})
        opts = dict(options)
        result = generate_group_wordcloud(batch_path, employee_id, filters, opts)
        if result:
            return {
                'value': v['value'],
                'wordcloud_url': result['wordcloud_url'],
                'evaluation_count': v['count'],
                'wordcloud_info': result['wordcloud_info'],
            }
        return {
            'value': v['value'],
            'wordcloud_url': None,
            'evaluation_count': v['count'],
            'warning': f"생성 실패 (평가 {v['count']}개)",
        }

    num_workers = min(multiprocessing.cpu_count(), 4)
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(process_value, v): v for v in group_values}
        for future in as_completed(futures):
            r = future.result()
            results[r['value']] = {
                'wordcloud_url': r['wordcloud_url'],
                'evaluation_count': r['evaluation_count'],
                'warning': r.get('warning'),
                'wordcloud_info': r.get('wordcloud_info'),
            }

    return results
