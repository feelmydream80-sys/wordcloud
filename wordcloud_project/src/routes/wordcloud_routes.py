"""Wordcloud generation routes for the WordCloud application."""

from flask import Blueprint, request, jsonify, send_from_directory, session
from src.services.wordcloud_service import (
    regenerate_wordcloud,
    serve_batch_wordcloud
)
from src.config.settings import OUTPUTS_DIR_PATH

wordcloud_bp = Blueprint('wordcloud', __name__, url_prefix='/api/wordcloud')


@wordcloud_bp.route('/regenerate', methods=['POST'])
def regenerate():
    """Regenerate wordcloud with specific parameters."""
    try:
        data = request.json
        result = regenerate_wordcloud(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@wordcloud_bp.route('/batch/<batch_name>/word/<filename>')
def serve_batch(batch_name, filename):
    """Serve wordcloud file from batch processing."""
    try:
        result = serve_batch_wordcloud(batch_name, filename)
        return result
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@wordcloud_bp.route('/outputs/<path:filename>')
def serve_outputs(filename):
    """Serve wordcloud file from outputs directory."""
    try:
        return send_from_directory(OUTPUTS_DIR_PATH, filename)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@wordcloud_bp.route('/update_pos', methods=['POST'])
def update_pos():
    """Update wordcloud part-of-speech configuration."""
    try:
        data = request.json
        from src.services.wordcloud_service import update_wordcloud_pos
        result = update_wordcloud_pos(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500