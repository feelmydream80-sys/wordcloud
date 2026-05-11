"""Perspective analysis routes - multi-filter grouping API."""

from flask import Blueprint, request, jsonify
from src.services.perspective_service import (
    load_batch_summary,
    get_groupable_columns,
    get_column_values,
    get_employee_list,
    generate_group_wordcloud,
    generate_all_group_wordclouds,
)

perspective_bp = Blueprint('perspective', __name__, url_prefix='/api/perspective')


@perspective_bp.route('/employees', methods=['POST'])
def api_get_employees():
    data = request.get_json(silent=True) or {}
    batch_path = data.get('batch_path')
    if not batch_path:
        return jsonify({'success': False, 'error': 'batch_path가 필요합니다.'}), 400

    batch_summary = load_batch_summary(batch_path)
    if not batch_summary:
        return jsonify({'success': False, 'error': 'batch_summary.json을 찾을 수 없습니다.'}), 404

    employees = get_employee_list(batch_summary)
    return jsonify({
        'success': True,
        'employees': employees,
        'batch_info': {
            'total_evaluations': batch_summary.get('batch_info', {}).get('total_evaluations', 0),
            'unique_employees': batch_summary.get('batch_info', {}).get('unique_employees', 0),
        }
    })


@perspective_bp.route('/columns', methods=['POST'])
def api_get_columns():
    data = request.get_json(silent=True) or {}
    batch_path = data.get('batch_path')
    if not batch_path:
        return jsonify({'success': False, 'error': 'batch_path가 필요합니다.'}), 400

    batch_summary = load_batch_summary(batch_path)
    if not batch_summary:
        return jsonify({'success': False, 'error': 'batch_summary.json을 찾을 수 없습니다.'}), 404

    columns = get_groupable_columns(batch_summary)
    return jsonify({
        'success': True,
        'columns': columns,
        'batch_info': {
            'total_evaluations': batch_summary.get('batch_info', {}).get('total_evaluations', 0),
            'unique_employees': batch_summary.get('batch_info', {}).get('unique_employees', 0),
        }
    })


@perspective_bp.route('/values', methods=['POST'])
def api_get_values():
    data = request.get_json(silent=True) or {}
    batch_path = data.get('batch_path')
    raw_field = data.get('column_name')
    employee_id = data.get('employee_id')

    if not batch_path or not raw_field:
        return jsonify({'success': False, 'error': 'batch_path와 column_name이 필요합니다.'}), 400
    if not employee_id:
        return jsonify({'success': False, 'error': 'employee_id가 필요합니다.'}), 400

    batch_summary = load_batch_summary(batch_path)
    if not batch_summary:
        return jsonify({'success': False, 'error': 'batch_summary.json을 찾을 수 없습니다.'}), 404

    values = get_column_values(batch_summary, raw_field, employee_id)
    return jsonify({
        'success': True,
        'column_name': raw_field,
        'employee_id': employee_id,
        'values': values,
        'total': len(values),
    })


@perspective_bp.route('/wordcloud', methods=['POST'])
def api_generate_wordcloud():
    """Generate wordcloud with multi-filter conditions (AND logic).

    Request format:
    {
      "batch_path": "...",
      "employee_id": "U001",
      "filters": [
        {"column": "evaluator_position", "value": "과장"},
        {"column": "evaluation_date__year", "value": "2026"}
      ],
      ...options...
    }

    Legacy single-filter format (still supported):
    {
      "column_name": "evaluator_position",
      "column_value": "과장",
      ...
    }
    """
    data = request.get_json(silent=True) or {}
    batch_path = data.get('batch_path')
    employee_id = data.get('employee_id')

    # Parse filters: new multi-filter format or legacy single filter
    filters = data.get('filters')
    if not filters:
        # Legacy fallback: single column_name + column_value
        col = data.get('column_name')
        val = data.get('column_value')
        if col and val is not None:
            filters = [{'column': col, 'value': val}]

    if not batch_path or not employee_id or not filters:
        return jsonify({
            'success': False,
            'error': 'batch_path, employee_id, filters가 필요합니다.'
        }), 400

    options = {
        'wordcloud_pos': data.get('wordcloud_pos', ['Noun']),
        'background_color': data.get('background_color', 'white'),
        'apply_emotion_colors': data.get('apply_emotion_colors', True),
        'remove_profanity': data.get('remove_profanity', False),
        'width': data.get('width', 800),
        'height': data.get('height', 600),
        'max_words': data.get('max_words', 100),
    }

    result = generate_group_wordcloud(batch_path, employee_id, filters, options)
    if result is None:
        flist = ', '.join(f"{f.get('column','?')}={f.get('value','?')}" for f in filters)
        return jsonify({
            'success': False,
            'error': f"'{employee_id}' 직원의 조건({flist})에 맞는 평가가 없습니다."
        }), 400

    return jsonify({'success': True, **result})


@perspective_bp.route('/groups', methods=['POST'])
def api_generate_groups():
    """Generate wordclouds for ALL distinct values in group_column.

    Request format:
    {
      "batch_path": "...",
      "employee_id": "U001",
      "group_column": "evaluator_position",
      "filters": [{"column": "evaluation_date__year", "value": "2026"}],  // pre-filters
      ...options...
    }
    """
    data = request.get_json(silent=True) or {}
    batch_path = data.get('batch_path')
    employee_id = data.get('employee_id')
    group_column = data.get('group_column', data.get('column_name'))
    prefilters = data.get('filters', [])

    if not batch_path or not employee_id or not group_column:
        return jsonify({
            'success': False,
            'error': 'batch_path, employee_id, group_column이 필요합니다.'
        }), 400

    options = {
        'wordcloud_pos': data.get('wordcloud_pos', ['Noun']),
        'background_color': data.get('background_color', 'white'),
        'apply_emotion_colors': data.get('apply_emotion_colors', True),
        'remove_profanity': data.get('remove_profanity', False),
        'width': data.get('width', 800),
        'height': data.get('height', 600),
        'max_words': data.get('max_words', 100),
    }

    results = generate_all_group_wordclouds(batch_path, employee_id, group_column, prefilters, options)
    if results is None:
        return jsonify({'success': False, 'error': 'batch_summary.json을 찾을 수 없습니다.'}), 404

    return jsonify({
        'success': True,
        'employee_id': employee_id,
        'group_column': group_column,
        'filters': prefilters,
        'groups': results,
    })
