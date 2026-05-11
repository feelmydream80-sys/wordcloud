"""Perspective analysis routes - generic column-based grouping API."""

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
    """Get list of employees in a batch."""
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
    """Get list of groupable columns from batch data."""
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
    """Get unique values + counts for a specific column, filtered by employee."""
    data = request.get_json(silent=True) or {}
    batch_path = data.get('batch_path')
    column_name = data.get('column_name')
    employee_id = data.get('employee_id')

    if not batch_path or not column_name:
        return jsonify({'success': False, 'error': 'batch_path와 column_name이 필요합니다.'}), 400

    if not employee_id:
        return jsonify({'success': False, 'error': 'employee_id가 필요합니다.'}), 400

    batch_summary = load_batch_summary(batch_path)
    if not batch_summary:
        return jsonify({'success': False, 'error': 'batch_summary.json을 찾을 수 없습니다.'}), 404

    values = get_column_values(batch_summary, column_name, employee_id)

    return jsonify({
        'success': True,
        'column_name': column_name,
        'employee_id': employee_id,
        'values': values,
        'total': len(values),
    })


@perspective_bp.route('/wordcloud', methods=['POST'])
def api_generate_wordcloud():
    """Generate wordcloud for one employee, filtered by column_name == column_value."""
    data = request.get_json(silent=True) or {}
    batch_path = data.get('batch_path')
    employee_id = data.get('employee_id')
    column_name = data.get('column_name')
    column_value = data.get('column_value')

    if not batch_path or not employee_id or not column_name or column_value is None:
        return jsonify({
            'success': False,
            'error': 'batch_path, employee_id, column_name, column_value가 모두 필요합니다.'
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

    result = generate_group_wordcloud(batch_path, employee_id, column_name, column_value, options)

    if result is None:
        return jsonify({
            'success': False,
            'error': f"'{employee_id}' 직원의 '{column_name}={column_value}' 조건에 맞는 평가가 없습니다."
        }), 400

    return jsonify({'success': True, **result})


@perspective_bp.route('/groups', methods=['POST'])
def api_generate_groups():
    """Generate wordclouds for ALL distinct values in a column, for ONE employee."""
    data = request.get_json(silent=True) or {}
    batch_path = data.get('batch_path')
    employee_id = data.get('employee_id')
    column_name = data.get('column_name')

    if not batch_path or not employee_id or not column_name:
        return jsonify({
            'success': False,
            'error': 'batch_path, employee_id, column_name이 모두 필요합니다.'
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

    results = generate_all_group_wordclouds(batch_path, employee_id, column_name, options)

    if results is None:
        return jsonify({
            'success': False,
            'error': 'batch_summary.json을 찾을 수 없습니다.'
        }), 404

    return jsonify({'success': True, 'employee_id': employee_id, 'groups': results})
