from flask import Blueprint, request, jsonify
import pandas as pd
import numpy as np
from app.database.db import get_db
from app.models.analysis import analyze_data, calculate_what_if

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/upload', methods=['POST'])
def upload():
    """Upload and process CSV file."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    model_name = request.form.get('name', 'Unnamed Model')
    description = request.form.get('description', '')
    
    try:
        # Read CSV file
        df = pd.read_csv(file)
        
        # Store in database and analyze
        model_id = store_data(df, model_name, description)
        analysis_results = analyze_data(model_id)
        
        return jsonify({
            'success': True,
            'model_id': model_id,
            'summary': {
                'teams': len(df),
                'seasons': df['season_year'].nunique(),
                'playoff_teams': df['made_playoffs'].sum()
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/benchmarks', methods=['GET'])
def get_benchmarks():
    """Get benchmark data for a specific model."""
    model_id = request.args.get('model_id')
    
    if not model_id:
        # Get the latest model if none specified
        db = get_db()
        model = db.execute('SELECT id FROM models ORDER BY created_timestamp DESC LIMIT 1').fetchone()
        
        if not model:
            return jsonify({'error': 'No models found'}), 404
        
        model_id = model['id']
    
    try:
        benchmarks = get_benchmark_data(model_id)
        correlations = get_correlation_data(model_id)
        
        return jsonify({
            'model_id': model_id,
            'benchmarks': benchmarks,
            'correlations': correlations
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/what-if', methods=['POST'])
def what_if():
    """Calculate what-if scenario based on adjusted values."""
    data = request.json
    
    if not data or 'model_id' not in data or 'adjustments' not in data:
        return jsonify({'error': 'Invalid request data'}), 400
    
    try:
        model_id = data['model_id']
        adjustments = data['adjustments']
        
        results = calculate_what_if(model_id, adjustments)
        
        return jsonify({
            'model_id': model_id,
            'results': results
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/models', methods=['GET'])
def get_models():
    """Get list of all analysis models."""
    try:
        db = get_db()
        models = db.execute(
            'SELECT id, name, description, created_timestamp FROM models ORDER BY created_timestamp DESC'
        ).fetchall()
        
        return jsonify({
            'models': [dict(model) for model in models]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/models/<int:model_id>', methods=['DELETE'])
def delete_model(model_id):
    """Delete a specific model and its associated data."""
    try:
        db = get_db()
        db.execute('DELETE FROM models WHERE id = ?', (model_id,))
        db.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def store_data(df, model_name, description):
    """Store uploaded data in the database."""
    db = get_db()
    
    # Create new model entry
    cursor = db.execute(
        'INSERT INTO models (name, description) VALUES (?, ?)',
        (model_name, description)
    )
    model_id = cursor.lastrowid
    
    # Store team data
    for _, row in df.iterrows():
        cursor = db.execute(
            'INSERT INTO teams (model_id, team_name, season_year, made_playoffs, wins, losses, ties) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (model_id, row['team_name'], row['season_year'], row['made_playoffs'], row['wins'], row['losses'], row['ties'])
        )
        team_id = cursor.lastrowid
        
        # Store statistics for each team
        for category in ['HR', 'RBI', 'R', 'SB', 'AVG', 'ERA', 'WHIP', 'W', 'SV_H', 'K']:
            if category in row:
                db.execute(
                    'INSERT INTO statistics (team_id, category, value) VALUES (?, ?, ?)',
                    (team_id, category, row[category])
                )
    
    db.commit()
    return model_id

def get_benchmark_data(model_id):
    """Retrieve benchmark data for a specific model."""
    db = get_db()
    benchmarks = db.execute(
        'SELECT category, mean_value, median_value, std_dev, min_value, max_value FROM benchmarks WHERE model_id = ?',
        (model_id,)
    ).fetchall()
    
    return [dict(benchmark) for benchmark in benchmarks]

def get_correlation_data(model_id):
    """Retrieve correlation data for a specific model."""
    db = get_db()
    correlations = db.execute(
        'SELECT category1, category2, coefficient FROM correlations WHERE model_id = ?',
        (model_id,)
    ).fetchall()
    
    return [dict(correlation) for correlation in correlations]