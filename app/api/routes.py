from flask import Blueprint, request, jsonify, current_app
import pandas as pd
import numpy as np
import os
import tempfile
import json
from werkzeug.utils import secure_filename
from app.database.db import get_db
from app.models.analysis import analyze_data, calculate_what_if

bp = Blueprint('api', __name__, url_prefix='/api')

# Custom JSON encoder to handle NumPy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super(NumpyEncoder, self).default(obj)

@bp.route('/upload', methods=['POST'])
def upload():
    """Upload and process CSV file.
    
    This endpoint handles:
    1. CSV file upload
    2. Data validation
    3. Storing raw data in SQLite
    4. Triggering statistical analysis
    5. Storing analysis results in SQLite
    6. Returning success message with summary and analysis ID
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    model_name = request.form.get('name', 'Unnamed Model')
    description = request.form.get('description', '')
    
    try:
        # Save the file temporarily to ensure it's properly read
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(temp_path)
        
        # Read CSV file
        df = pd.read_csv(temp_path)
        
        # Validate required columns
        required_columns = ['team_name', 'season_year', 'made_playoffs', 'wins', 'losses', 'ties']
        stat_columns = ['HR', 'RBI', 'R', 'SB', 'AVG', 'ERA', 'WHIP', 'W', 'SV_H', 'K']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        missing_stats = [col for col in stat_columns if col not in df.columns]
        
        if missing_columns:
            return jsonify({
                'error': f'Missing required columns: {", ".join(missing_columns)}'
            }), 400
        
        if missing_stats:
            return jsonify({
                'error': f'Missing statistical columns: {", ".join(missing_stats)}'
            }), 400
        
        # Convert made_playoffs to boolean/integer
        df['made_playoffs'] = df['made_playoffs'].astype(bool).astype(int)
        
        # Clean up temporary file
        os.remove(temp_path)
        
        # Store in database
        model_id = store_data(df, model_name, description)
        
        # Perform statistical analysis
        analysis_results = analyze_data(model_id)
        
        # Convert NumPy values to Python native types
        teams_count = int(len(df))
        seasons_count = int(df['season_year'].nunique())
        playoff_teams_count = int(df['made_playoffs'].sum())
        non_playoff_teams_count = int(teams_count - playoff_teams_count)
        
        # Return success with summary
        return jsonify({
            'success': True,
            'model_id': model_id,
            'summary': {
                'teams': teams_count,
                'seasons': seasons_count,
                'playoff_teams': playoff_teams_count,
                'non_playoff_teams': non_playoff_teams_count,
                'categories_analyzed': len(stat_columns),
                'benchmarks_generated': len(analysis_results['benchmarks']),
                'correlations_calculated': len(analysis_results['correlations'])
            }
        })
    except pd.errors.EmptyDataError:
        return jsonify({'error': 'The CSV file is empty'}), 400
    except pd.errors.ParserError:
        return jsonify({'error': 'Could not parse the CSV file. Please check the format.'}), 400
    except Exception as e:
        current_app.logger.error(f"Error processing upload: {str(e)}")
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
    """Store uploaded data in the database.
    
    This function:
    1. Creates a new model entry
    2. Stores team data for each row in the dataframe
    3. Stores statistics for each team
    
    Args:
        df: Pandas DataFrame containing the CSV data
        model_name: Name of the model
        description: Description of the model
        
    Returns:
        model_id: ID of the created model
    """
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
            (
                model_id, 
                row['team_name'], 
                int(row['season_year']), 
                bool(row['made_playoffs']), 
                int(row['wins']), 
                int(row['losses']), 
                int(row['ties'])
            )
        )
        team_id = cursor.lastrowid
        
        # Store statistics for each team
        for category in ['HR', 'RBI', 'R', 'SB', 'AVG', 'ERA', 'WHIP', 'W', 'SV_H', 'K']:
            if category in row:
                db.execute(
                    'INSERT INTO statistics (team_id, category, value) VALUES (?, ?, ?)',
                    (team_id, category, float(row[category]))
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
    
    # Convert to dict and ensure all numeric values are Python native types
    result = []
    for benchmark in benchmarks:
        benchmark_dict = dict(benchmark)
        for key in ['mean_value', 'median_value', 'std_dev', 'min_value', 'max_value']:
            if key in benchmark_dict and benchmark_dict[key] is not None:
                benchmark_dict[key] = float(benchmark_dict[key])
        result.append(benchmark_dict)
    
    return result

def get_correlation_data(model_id):
    """Retrieve correlation data for a specific model."""
    db = get_db()
    correlations = db.execute(
        'SELECT category1, category2, coefficient FROM correlations WHERE model_id = ?',
        (model_id,)
    ).fetchall()
    
    # Convert to dict and ensure coefficient is a Python native float
    result = []
    for correlation in correlations:
        corr_dict = dict(correlation)
        if 'coefficient' in corr_dict and corr_dict['coefficient'] is not None:
            corr_dict['coefficient'] = float(corr_dict['coefficient'])
        result.append(corr_dict)
    
    return result