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

@bp.route('/standings', methods=['GET'])
def get_standings():
    """Get all records from the Standings table."""
    try:
        db = get_db()
        standings = db.execute(
            'SELECT ModelId, Description, R, HR, RBI, SB, AVG, W, K, ERA, WHIP, SVH FROM Standings'
        ).fetchall()
        
        # Convert to list of dictionaries and ensure numeric values are Python native types
        result = []
        for standing in standings:
            standing_dict = dict(standing)
            # Convert numeric fields to appropriate Python types
            for key in ['R', 'HR', 'RBI', 'SB', 'W', 'K', 'SVH']:
                if key in standing_dict and standing_dict[key] is not None:
                    standing_dict[key] = int(standing_dict[key])
            for key in ['AVG', 'ERA', 'WHIP']:
                if key in standing_dict and standing_dict[key] is not None:
                    standing_dict[key] = float(standing_dict[key])
            result.append(standing_dict)
        
        return jsonify({
            'standings': result
        })
    except Exception as e:
        current_app.logger.error(f"Error retrieving standings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/standings/<int:model_id>', methods=['GET'])
def get_standing(model_id):
    """Get a specific standing by ModelId."""
    try:
        db = get_db()
        standing = db.execute(
            'SELECT ModelId, Description, R, HR, RBI, SB, AVG, W, K, ERA, WHIP, SVH FROM Standings WHERE ModelId = ?',
            (model_id,)
        ).fetchone()
        
        if not standing:
            return jsonify({'error': f'No standing found with ModelId {model_id}'}), 404
        
        # Convert to dictionary and ensure numeric values are Python native types
        standing_dict = dict(standing)
        # Convert numeric fields to appropriate Python types
        for key in ['R', 'HR', 'RBI', 'SB', 'W', 'K', 'SVH']:
            if key in standing_dict and standing_dict[key] is not None:
                standing_dict[key] = int(standing_dict[key])
        for key in ['AVG', 'ERA', 'WHIP']:
            if key in standing_dict and standing_dict[key] is not None:
                standing_dict[key] = float(standing_dict[key])
        
        return jsonify(standing_dict)
    except Exception as e:
        current_app.logger.error(f"Error retrieving standing with ModelId {model_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams', methods=['GET'])
def get_teams():
    """Get all records from the Teams table."""
    try:
        db = get_db()
        teams = db.execute(
            'SELECT TeamId, TeamName, Owner, Salary FROM Teams'
        ).fetchall()
        
        # Convert to list of dictionaries and ensure numeric values are Python native types
        result = []
        for team in teams:
            team_dict = dict(team)
            # Convert numeric fields to appropriate Python types
            if 'Salary' in team_dict and team_dict['Salary'] is not None:
                team_dict['Salary'] = float(team_dict['Salary'])
            result.append(team_dict)
        
        return jsonify({
            'teams': result
        })
    except Exception as e:
        current_app.logger.error(f"Error retrieving teams: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams/<int:team_id>', methods=['GET'])
def get_team(team_id):
    """Get a specific team by TeamId."""
    try:
        db = get_db()
        team = db.execute(
            'SELECT TeamId, TeamName, Owner, Salary FROM Teams WHERE TeamId = ?',
            (team_id,)
        ).fetchone()
        
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Convert to dictionary and ensure numeric values are Python native types
        team_dict = dict(team)
        # Convert numeric fields to appropriate Python types
        if 'Salary' in team_dict and team_dict['Salary'] is not None:
            team_dict['Salary'] = float(team_dict['Salary'])
        
        return jsonify(team_dict)
    except Exception as e:
        current_app.logger.error(f"Error retrieving team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams/<int:team_id>/roster', methods=['GET'])
def get_team_roster(team_id):
    """Get a team's complete roster including hitters and pitchers."""
    try:
        db = get_db()
        # First check if the team exists
        team = db.execute(
            'SELECT TeamId, TeamName, Owner, Salary FROM Teams WHERE TeamId = ?',
            (team_id,)
        ).fetchone()
        
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Get team basic info
        team_dict = dict(team)
        if 'Salary' in team_dict and team_dict['Salary'] is not None:
            team_dict['Salary'] = float(team_dict['Salary'])
        
        # Get team hitters
        hitters = db.execute('''
            SELECT h.* FROM Hitters h
            WHERE h.HittingTeamId = ?
        ''', (team_id,)).fetchall()
        
        hitters_list = []
        for hitter in hitters:
            hitter_dict = dict(hitter)
            # Convert numeric fields to appropriate Python types
            for key in ['Age', 'G', 'PA', 'AB', 'H', 'HR', 'R', 'RBI', 'BB', 'HBP', 'SB']:
                if key in hitter_dict and hitter_dict[key] is not None:
                    hitter_dict[key] = int(hitter_dict[key])
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG']:
                if key in hitter_dict and hitter_dict[key] is not None:
                    hitter_dict[key] = float(hitter_dict[key])
            hitters_list.append(hitter_dict)
        
        # Get team pitchers
        pitchers = db.execute('''
            SELECT p.* FROM Pitchers p
            WHERE p.PitchingTeamId = ?
        ''', (team_id,)).fetchall()
        
        pitchers_list = []
        for pitcher in pitchers:
            pitcher_dict = dict(pitcher)
            # Convert numeric fields to appropriate Python types
            for key in ['Age', 'W', 'QS', 'G', 'SV', 'HLD', 'SVH', 'IP', 'SO']:
                if key in pitcher_dict and pitcher_dict[key] is not None:
                    pitcher_dict[key] = int(pitcher_dict[key])
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9']:
                if key in pitcher_dict and pitcher_dict[key] is not None:
                    pitcher_dict[key] = float(pitcher_dict[key])
            pitchers_list.append(pitcher_dict)
        
        # Combine all data
        result = {
            'team': team_dict,
            'hitters': hitters_list,
            'pitchers': pitchers_list
        }
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error retrieving roster for team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams/<int:team_id>/hitters', methods=['GET'])
def get_team_hitters(team_id):
    """Get all hitters for a specific team."""
    try:
        db = get_db()
        # First check if the team exists
        team = db.execute(
            'SELECT TeamId, TeamName, Owner, Salary FROM Teams WHERE TeamId = ?',
            (team_id,)
        ).fetchone()
        
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Get team basic info
        team_dict = dict(team)
        if 'Salary' in team_dict and team_dict['Salary'] is not None:
            team_dict['Salary'] = float(team_dict['Salary'])
        
        # Get team hitters
        hitters = db.execute('''
            SELECT h.* FROM Hitters h
            WHERE h.HittingTeamId = ?
        ''', (team_id,)).fetchall()
        
        hitters_list = []
        for hitter in hitters:
            hitter_dict = dict(hitter)
            # Convert numeric fields to appropriate Python types
            for key in ['Age', 'G', 'PA', 'AB', 'H', 'HR', 'R', 'RBI', 'BB', 'HBP', 'SB']:
                if key in hitter_dict and hitter_dict[key] is not None:
                    hitter_dict[key] = int(hitter_dict[key])
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG']:
                if key in hitter_dict and hitter_dict[key] is not None:
                    hitter_dict[key] = float(hitter_dict[key])
            hitters_list.append(hitter_dict)
        
        # Return team info and hitters
        result = {
            'team': team_dict,
            'hitters': hitters_list
        }
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error retrieving hitters for team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams/<int:team_id>/pitchers', methods=['GET'])
def get_team_pitchers(team_id):
    """Get all pitchers for a specific team."""
    try:
        db = get_db()
        # First check if the team exists
        team = db.execute(
            'SELECT TeamId, TeamName, Owner, Salary FROM Teams WHERE TeamId = ?',
            (team_id,)
        ).fetchone()
        
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Get team basic info
        team_dict = dict(team)
        if 'Salary' in team_dict and team_dict['Salary'] is not None:
            team_dict['Salary'] = float(team_dict['Salary'])
        
        # Get team pitchers
        pitchers = db.execute('''
            SELECT p.* FROM Pitchers p
            WHERE p.PitchingTeamId = ?
        ''', (team_id,)).fetchall()
        
        pitchers_list = []
        for pitcher in pitchers:
            pitcher_dict = dict(pitcher)
            # Convert numeric fields to appropriate Python types
            for key in ['Age', 'W', 'QS', 'G', 'SV', 'HLD', 'SVH', 'IP', 'SO']:
                if key in pitcher_dict and pitcher_dict[key] is not None:
                    pitcher_dict[key] = int(pitcher_dict[key])
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9', 'BABIP', 'FIP']:
                if key in pitcher_dict and pitcher_dict[key] is not None:
                    pitcher_dict[key] = float(pitcher_dict[key])
            pitchers_list.append(pitcher_dict)
        
        # Return team info and pitchers
        result = {
            'team': team_dict,
            'pitchers': pitchers_list
        }
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error retrieving pitchers for team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Valid position names for TeamHitters table
HITTER_POSITIONS = [
    'C', 'FirstBase', 'SecondBase', 'ShortStop', 'ThirdBase', 
    'MiddleInfielder', 'CornerInfielder', 'Outfield1', 'Outfield2', 
    'Outfield3', 'Outfield4', 'Outfield5', 'Utility', 
    'Bench1', 'Bench2', 'Bench3'
]

# Valid position names for TeamPitchers table
PITCHER_POSITIONS = [
    'Pitcher1', 'Pitcher2', 'Pitcher3', 'Pitcher4', 'Pitcher5',
    'Pitcher6', 'Pitcher7', 'Pitcher8', 'Pitcher9',
    'Bench1', 'Bench2', 'Bench3'
]

# Mapping of roster positions to actual player positions
POSITION_MAPPING = {
    'C': ['C'],
    'FirstBase': ['1B'],
    'SecondBase': ['2B'],
    'ShortStop': ['SS'],
    'ThirdBase': ['3B'],
    'MiddleInfielder': ['2B', 'SS'],
    'CornerInfielder': ['1B', '3B'],
    'Outfield1': ['OF'],
    'Outfield2': ['OF'],
    'Outfield3': ['OF'],
    'Outfield4': ['OF'],
    'Outfield5': ['OF'],
    'Utility': ['C', '1B', '2B', 'SS', '3B', 'OF', 'DH'],  # Any position
    'Bench1': ['C', '1B', '2B', 'SS', '3B', 'OF', 'DH'],   # Any position
    'Bench2': ['C', '1B', '2B', 'SS', '3B', 'OF', 'DH'],   # Any position
    'Bench3': ['C', '1B', '2B', 'SS', '3B', 'OF', 'DH']    # Any position
}

@bp.route('/teams/<int:team_id>/roster/update', methods=['POST'])
def update_team_roster(team_id):
    """Update a team's roster by adding, removing, or changing a player at a specific position.
    
    Request body should contain:
    {
        "player_type": "hitter" or "pitcher",
        "position": position name (from HITTER_POSITIONS or PITCHER_POSITIONS),
        "player_id": ID of the player to assign (or null/None to remove)
    }
    """
    try:
        db = get_db()
        data = request.json
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['player_type', 'position']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400
        
        player_type = data['player_type'].lower()
        position = data['position']
        player_id = data.get('player_id')  # Can be None to remove a player
        
        # Validate player_type
        if player_type not in ['hitter', 'pitcher']:
            return jsonify({'error': 'player_type must be either "hitter" or "pitcher"'}), 400
        
        # Validate position based on player_type
        valid_positions = HITTER_POSITIONS if player_type == 'hitter' else PITCHER_POSITIONS
        if position not in valid_positions:
            return jsonify({'error': f'Invalid position for {player_type}. Must be one of: {", ".join(valid_positions)}'}), 400
        
        # Check if team exists
        team = db.execute('SELECT TeamId FROM Teams WHERE TeamId = ?', (team_id,)).fetchone()
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Check if player exists and is eligible for the position (if player_id is provided)
        if player_id is not None:
            if player_type == 'hitter':
                player = db.execute('SELECT HittingPlayerId, Position FROM Hitters WHERE HittingPlayerId = ?', (player_id,)).fetchone()
                if not player:
                    return jsonify({'error': f'No hitter found with HittingPlayerId {player_id}'}), 404
                
                # Check position eligibility (except for utility and bench positions which can be any position)
                if position not in ['Utility', 'Bench1', 'Bench2', 'Bench3']:
                    eligible_positions = POSITION_MAPPING.get(position, [])
                    
                    # Split the Position field by commas to handle multiple positions
                    # For example, a player with Position="2B,SS,3B,OF" will have
                    # player_positions = ["2B", "SS", "3B", "OF"]
                    player_positions = player['Position'].split(',') if player['Position'] else []
                    
                    # Check if player is eligible for any of the required positions
                    # A player is eligible if ANY of their positions matches ANY of the eligible positions
                    # For example, a player with positions ["2B", "SS", "3B", "OF"] would be eligible for:
                    # - SecondBase (requires "2B")
                    # - ShortStop (requires "SS")
                    # - ThirdBase (requires "3B")
                    # - MiddleInfielder (requires "2B" or "SS")
                    # - CornerInfielder (requires "1B" or "3B")
                    # - Outfield1-5 (requires "OF")
                    is_eligible = False
                    for pos in player_positions:
                        pos = pos.strip()  # Remove any whitespace
                        if pos in eligible_positions:
                            is_eligible = True
                            break
                    
                    if not is_eligible:
                        return jsonify({
                            'error': f'Player with HittingPlayerId {player_id} is not eligible for position {position}. ' +
                                    f'Player positions: {player["Position"]}, Required positions: {", ".join(eligible_positions)}'
                        }), 400
            else:  # pitcher
                player = db.execute('SELECT PitchingPlayerId FROM Pitchers WHERE PitchingPlayerId = ?', (player_id,)).fetchone()
                if not player:
                    return jsonify({'error': f'No pitcher found with PitchingPlayerId {player_id}'}), 404
        
        # Update the team roster
        if player_type == 'hitter':
            # Check if TeamHitters record exists for this team
            team_hitters = db.execute('SELECT HittingTeamId FROM TeamHitters WHERE HittingTeamId = ?', (team_id,)).fetchone()
            
            if team_hitters:
                # Update existing record
                db.execute(f'UPDATE TeamHitters SET {position} = ? WHERE HittingTeamId = ?', (player_id, team_id))
            else:
                # Create new record with all positions set to NULL except the one being updated
                columns = ', '.join(['HittingTeamId'] + HITTER_POSITIONS)
                placeholders = ', '.join(['?'] + ['?'] * len(HITTER_POSITIONS))
                
                # Create values array with NULL for all positions except the one being updated
                values = [team_id] + [None] * len(HITTER_POSITIONS)
                position_index = HITTER_POSITIONS.index(position)
                values[position_index + 1] = player_id  # +1 because team_id is the first value
                
                db.execute(f'INSERT INTO TeamHitters ({columns}) VALUES ({placeholders})', values)
            
            # If player_id is provided, update the player's team reference
            if player_id is not None:
                db.execute('UPDATE Hitters SET HittingTeamId = ? WHERE HittingPlayerId = ?', (team_id, player_id))
            
        else:  # pitcher
            # Check if TeamPitchers record exists for this team
            team_pitchers = db.execute('SELECT PitchingTeamId FROM TeamPitchers WHERE PitchingTeamId = ?', (team_id,)).fetchone()
            
            if team_pitchers:
                # Update existing record
                db.execute(f'UPDATE TeamPitchers SET {position} = ? WHERE PitchingTeamId = ?', (player_id, team_id))
            else:
                # Create new record with all positions set to NULL except the one being updated
                columns = ', '.join(['PitchingTeamId'] + PITCHER_POSITIONS)
                placeholders = ', '.join(['?'] + ['?'] * len(PITCHER_POSITIONS))
                
                # Create values array with NULL for all positions except the one being updated
                values = [team_id] + [None] * len(PITCHER_POSITIONS)
                position_index = PITCHER_POSITIONS.index(position)
                values[position_index + 1] = player_id  # +1 because team_id is the first value
                
                db.execute(f'INSERT INTO TeamPitchers ({columns}) VALUES ({placeholders})', values)
            
            # If player_id is provided, update the player's team reference
            if player_id is not None:
                db.execute('UPDATE Pitchers SET PitchingTeamId = ? WHERE PitchingPlayerId = ?', (team_id, player_id))
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'Updated {player_type} position {position} for team {team_id}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error updating roster for team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/players/available', methods=['GET'])
def get_available_players():
    """Get players that are not assigned to any team.
    
    Query parameters:
    - player_type: 'hitter' or 'pitcher' (required)
    - position: Filter by position (optional) - For hitters, this is the roster position (e.g., 'C', 'FirstBase', etc.)
    """
    try:
        player_type = request.args.get('player_type', '').lower()
        position = request.args.get('position')
        
        if not player_type or player_type not in ['hitter', 'pitcher']:
            return jsonify({'error': 'player_type parameter is required and must be either "hitter" or "pitcher"'}), 400
        
        db = get_db()
        
        if player_type == 'hitter':
            query = '''
                SELECT * FROM Hitters 
                WHERE HittingTeamId IS NULL
            '''
            
            # Add position filter if provided
            if position:
                if position not in HITTER_POSITIONS:
                    return jsonify({'error': f'Invalid hitter position. Must be one of: {", ".join(HITTER_POSITIONS)}'}), 400
                
                # Get the actual player positions for this roster position
                eligible_positions = POSITION_MAPPING.get(position, [])
                
                # No additional filtering needed for utility or bench positions (they can be any position)
                if position not in ['Utility', 'Bench1', 'Bench2', 'Bench3']:
                    players = db.execute(query).fetchall()
                    
                    # Filter players based on position eligibility
                    filtered_players = []
                    for player in players:
                        # Split the Position field by commas to handle multiple positions
                        # For example, a player with Position="2B,SS,3B,OF" will have
                        # player_positions = ["2B", "SS", "3B", "OF"]
                        player_positions = player['Position'].split(',') if player['Position'] else []
                        
                        # Check if player is eligible for any of the required positions
                        # A player is eligible if ANY of their positions matches ANY of the eligible positions
                        is_eligible = False
                        for pos in player_positions:
                            pos = pos.strip()  # Remove any whitespace
                            if pos in eligible_positions:
                                is_eligible = True
                                break
                        
                        if is_eligible:
                            filtered_players.append(player)
                    
                    players = filtered_players
                else:
                    # For utility and bench positions, all hitters are eligible
                    players = db.execute(query).fetchall()
            else:
                # No position filter, return all available hitters
                players = db.execute(query).fetchall()
            
            # Convert to list of dictionaries and ensure numeric values are Python native types
            result = []
            for player in players:
                player_dict = dict(player)
                # Convert numeric fields to appropriate Python types
                for key in ['Age', 'G', 'PA', 'AB', 'H', 'HR', 'R', 'RBI', 'BB', 'HBP', 'SB']:
                    if key in player_dict and player_dict[key] is not None:
                        player_dict[key] = int(player_dict[key])
                for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG']:
                    if key in player_dict and player_dict[key] is not None:
                        player_dict[key] = float(player_dict[key])
                result.append(player_dict)
        else:  # pitcher
            query = '''
                SELECT * FROM Pitchers 
                WHERE PitchingTeamId IS NULL
            '''
            
            # Add position filter if provided
            if position:
                query += ' AND Position = ?'
                players = db.execute(query, (position,)).fetchall()
            else:
                players = db.execute(query).fetchall()
            
            # Convert to list of dictionaries and ensure numeric values are Python native types
            result = []
            for player in players:
                player_dict = dict(player)
                # Convert numeric fields to appropriate Python types
                for key in ['Age', 'W', 'QS', 'G', 'SV', 'HLD', 'SVH', 'IP', 'SO']:
                    if key in player_dict and player_dict[key] is not None:
                        player_dict[key] = int(player_dict[key])
                for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9', 'BABIP', 'FIP']:
                    if key in player_dict and player_dict[key] is not None:
                        player_dict[key] = float(player_dict[key])
                result.append(player_dict)
        
        return jsonify({
            'player_type': player_type,
            'position': position,
            'players': result
        })
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving available players: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams/<int:team_id>/roster/structure', methods=['GET'])
def get_team_roster_structure(team_id):
    """Get the current roster structure for a team, showing which positions are filled and which are empty."""
    try:
        db = get_db()
        
        # Check if team exists
        team = db.execute('SELECT TeamId, TeamName, Owner, Salary FROM Teams WHERE TeamId = ?', (team_id,)).fetchone()
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Get team basic info
        team_dict = dict(team)
        if 'Salary' in team_dict and team_dict['Salary'] is not None:
            team_dict['Salary'] = float(team_dict['Salary'])
        
        # Get hitter positions
        hitter_positions = {}
        team_hitters = db.execute('SELECT * FROM TeamHitters WHERE HittingTeamId = ?', (team_id,)).fetchone()
        
        if team_hitters:
            team_hitters_dict = dict(team_hitters)
            for position in HITTER_POSITIONS:
                player_id = team_hitters_dict.get(position)
                if player_id:
                    # Get player details
                    player = db.execute('SELECT HittingPlayerId, PlayerName, Position, Status FROM Hitters WHERE HittingPlayerId = ?', (player_id,)).fetchone()
                    if player:
                        hitter_positions[position] = dict(player)
                    else:
                        # Handle case where player ID exists in TeamHitters but not in Hitters table
                        hitter_positions[position] = {'HittingPlayerId': player_id, 'PlayerName': 'Unknown Player', 'Position': 'Unknown', 'Status': 'Unknown'}
                else:
                    hitter_positions[position] = None
        else:
            # No TeamHitters record exists yet
            for position in HITTER_POSITIONS:
                hitter_positions[position] = None
        
        # Get pitcher positions
        pitcher_positions = {}
        team_pitchers = db.execute('SELECT * FROM TeamPitchers WHERE PitchingTeamId = ?', (team_id,)).fetchone()
        
        if team_pitchers:
            team_pitchers_dict = dict(team_pitchers)
            for position in PITCHER_POSITIONS:
                player_id = team_pitchers_dict.get(position)
                if player_id:
                    # Get player details
                    player = db.execute('SELECT PitchingPlayerId, PlayerName, Position, Status FROM Pitchers WHERE PitchingPlayerId = ?', (player_id,)).fetchone()
                    if player:
                        pitcher_positions[position] = dict(player)
                    else:
                        # Handle case where player ID exists in TeamPitchers but not in Pitchers table
                        pitcher_positions[position] = {'PitchingPlayerId': player_id, 'PlayerName': 'Unknown Player', 'Position': 'Unknown', 'Status': 'Unknown'}
                else:
                    pitcher_positions[position] = None
        else:
            # No TeamPitchers record exists yet
            for position in PITCHER_POSITIONS:
                pitcher_positions[position] = None
        
        return jsonify({
            'team': team_dict,
            'hitter_positions': hitter_positions,
            'pitcher_positions': pitcher_positions
        })
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving roster structure for team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams/<int:team_id>/stats/hitting', methods=['GET'])
def get_team_hitting_stats(team_id):
    """Calculate and return aggregate hitting statistics for a team.
    
    This calculates:
    - R, HR, RBI, SB: Sum of all hitters' values
    - AVG: Average of all hitters' AVG values
    """
    try:
        db = get_db()
        
        # Check if team exists
        team = db.execute('SELECT TeamId, TeamName, Owner FROM Teams WHERE TeamId = ?', (team_id,)).fetchone()
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Get team basic info
        team_dict = dict(team)
        
        # Get all hitters for this team
        hitters = db.execute('''
            SELECT h.* FROM Hitters h
            WHERE h.HittingTeamId = ?
        ''', (team_id,)).fetchall()
        
        if not hitters:
            # Return zeros if no hitters found
            return jsonify({
                'team': team_dict,
                'stats': {
                    'R': 0,
                    'HR': 0,
                    'RBI': 0,
                    'SB': 0,
                    'AVG': 0.0
                }
            })
        
        # Calculate aggregate stats
        total_r = 0
        total_hr = 0
        total_rbi = 0
        total_sb = 0
        total_avg = 0.0
        valid_avg_count = 0
        
        for hitter in hitters:
            # Sum up counting stats
            if hitter['R'] is not None:
                total_r += hitter['R']
            if hitter['HR'] is not None:
                total_hr += hitter['HR']
            if hitter['RBI'] is not None:
                total_rbi += hitter['RBI']
            if hitter['SB'] is not None:
                total_sb += hitter['SB']
            
            # Average the AVG stat
            if hitter['AVG'] is not None:
                total_avg += hitter['AVG']
                valid_avg_count += 1
        
        # Calculate average AVG
        avg = total_avg / valid_avg_count if valid_avg_count > 0 else 0.0
        
        return jsonify({
            'team': team_dict,
            'stats': {
                'R': total_r,
                'HR': total_hr,
                'RBI': total_rbi,
                'SB': total_sb,
                'AVG': round(avg, 3)  # Round to 3 decimal places
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error calculating hitting stats for team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams/<int:team_id>/stats/pitching', methods=['GET'])
def get_team_pitching_stats(team_id):
    """Calculate and return aggregate pitching statistics for a team.
    
    This calculates:
    - W, K, SVH: Sum of all pitchers' values
    - ERA, WHIP, BABIP, FIP: Average of all pitchers' values
    """
    try:
        db = get_db()
        
        # Check if team exists
        team = db.execute('SELECT TeamId, TeamName, Owner FROM Teams WHERE TeamId = ?', (team_id,)).fetchone()
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Get team basic info
        team_dict = dict(team)
        
        # Get all pitchers for this team
        pitchers = db.execute('''
            SELECT p.* FROM Pitchers p
            WHERE p.PitchingTeamId = ?
        ''', (team_id,)).fetchall()
        
        if not pitchers:
            # Return zeros if no pitchers found
            return jsonify({
                'team': team_dict,
                'stats': {
                    'W': 0,
                    'K': 0,
                    'SVH': 0,
                    'ERA': 0.0,
                    'WHIP': 0.0
                }
            })
        
        # Calculate aggregate stats
        total_w = 0
        total_k = 0
        total_svh = 0
        total_era = 0.0
        total_whip = 0.0
        total_babip = 0.0
        total_fip = 0.0
        valid_era_count = 0
        valid_whip_count = 0
        
        for pitcher in pitchers:
            # Sum up counting stats
            if pitcher['W'] is not None:
                total_w += pitcher['W']
            if pitcher['SO'] is not None:  # K is stored as SO in the database
                total_k += pitcher['SO']
            if pitcher['SVH'] is not None:
                total_svh += pitcher['SVH']
            
            # Average the ERA, WHIP, BABIP, and FIP stats
            if pitcher['ERA'] is not None:
                total_era += pitcher['ERA']
                valid_era_count += 1
            if pitcher['WHIP'] is not None:
                total_whip += pitcher['WHIP']
                valid_whip_count += 1
        
        # Calculate averages
        era = total_era / valid_era_count if valid_era_count > 0 else 0.0
        whip = total_whip / valid_whip_count if valid_whip_count > 0 else 0.0
        
        return jsonify({
            'team': team_dict,
            'stats': {
                'W': total_w,
                'K': total_k,
                'SVH': total_svh,
                'ERA': round(era, 2),  # Round to 2 decimal places
                'WHIP': round(whip, 3),  # Round to 3 decimal places
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error calculating pitching stats for team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/teams/<int:team_id>/stats', methods=['GET'])
def get_team_all_stats(team_id):
    """Calculate and return all aggregate statistics (hitting and pitching) for a team."""
    try:
        db = get_db()
        
        # Check if team exists
        team = db.execute('SELECT TeamId, TeamName, Owner FROM Teams WHERE TeamId = ?', (team_id,)).fetchone()
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # Get team basic info
        team_dict = dict(team)
        
        # Get all hitters for this team
        hitters = db.execute('''
            SELECT h.* FROM Hitters h
            WHERE h.HittingTeamId = ?
        ''', (team_id,)).fetchall()
        
        # Calculate hitting stats
        total_r = 0
        total_hr = 0
        total_rbi = 0
        total_sb = 0
        total_avg = 0.0
        valid_avg_count = 0
        
        for hitter in hitters:
            # Sum up counting stats
            if hitter['R'] is not None:
                total_r += hitter['R']
            if hitter['HR'] is not None:
                total_hr += hitter['HR']
            if hitter['RBI'] is not None:
                total_rbi += hitter['RBI']
            if hitter['SB'] is not None:
                total_sb += hitter['SB']
            
            # Average the AVG stat
            if hitter['AVG'] is not None:
                total_avg += hitter['AVG']
                valid_avg_count += 1
        
        # Calculate average AVG
        avg = total_avg / valid_avg_count if valid_avg_count > 0 else 0.0
        
        # Get all pitchers for this team
        pitchers = db.execute('''
            SELECT p.* FROM Pitchers p
            WHERE p.PitchingTeamId = ?
        ''', (team_id,)).fetchall()
        
        # Calculate pitching stats
        total_w = 0
        total_k = 0
        total_svh = 0
        total_era = 0.0
        total_whip = 0.0
        total_babip = 0.0
        total_fip = 0.0
        valid_era_count = 0
        valid_whip_count = 0
        
        for pitcher in pitchers:
            # Sum up counting stats
            if pitcher['W'] is not None:
                total_w += pitcher['W']
            if pitcher['SO'] is not None:  # K is stored as SO in the database
                total_k += pitcher['SO']
            if pitcher['SVH'] is not None:
                total_svh += pitcher['SVH']
            
            # Average the ERA, WHIP, BABIP, and FIP stats
            if pitcher['ERA'] is not None:
                total_era += pitcher['ERA']
                valid_era_count += 1
            if pitcher['WHIP'] is not None:
                total_whip += pitcher['WHIP']
                valid_whip_count += 1
        
        # Calculate averages
        era = total_era / valid_era_count if valid_era_count > 0 else 0.0
        whip = total_whip / valid_whip_count if valid_whip_count > 0 else 0.0
        
        return jsonify({
            'team': team_dict,
            'hitting_stats': {
                'R': total_r,
                'HR': total_hr,
                'RBI': total_rbi,
                'SB': total_sb,
                'AVG': round(avg, 3)  # Round to 3 decimal places
            },
            'pitching_stats': {
                'W': total_w,
                'K': total_k,
                'SVH': total_svh,
                'ERA': round(era, 2),  # Round to 2 decimal places
                'WHIP': round(whip, 3),  # Round to 3 decimal places
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error calculating stats for team with TeamId {team_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500