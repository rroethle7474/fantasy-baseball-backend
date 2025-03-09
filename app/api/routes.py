from flask import Blueprint, request, jsonify, current_app
import pandas as pd
import numpy as np
import os
import tempfile
import json
from werkzeug.utils import secure_filename
from app.database.db import get_db
from app.models.analysis import analyze_data, calculate_what_if
import pulp

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
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG', 'SGCalc']:
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
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9', 'BABIP', 'FIP', 'SGCalc']:
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
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG', 'SGCalc']:
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
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9', 'BABIP', 'FIP', 'SGCalc']:
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
        print("Updating roster for team", team_id)
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
        print("Player Id", player_id)
        print("Player Type", player_type)
        print("Position", position)
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
                # If removing a player, get the current player ID first before updating
                if player_id is None:
                    # Get the player currently in this position before removing
                    previous_player = db.execute(f'SELECT {position} FROM TeamHitters WHERE HittingTeamId = ?', (team_id,)).fetchone()
                    previous_player_id = previous_player[0] if previous_player and previous_player[0] is not None else None
                    
                    # Now update the TeamHitters table
                    db.execute(f'UPDATE TeamHitters SET {position} = NULL WHERE HittingTeamId = ?', (team_id,))
                    
                    # If there was a player in this position, update their team reference
                    if previous_player_id is not None:
                        db.execute('UPDATE Hitters SET HittingTeamId = NULL WHERE HittingPlayerId = ?', (previous_player_id,))
                else:
                    db.execute(f'UPDATE TeamHitters SET {position} = ? WHERE HittingTeamId = ?', (player_id, team_id))
                    # Update the player's team reference
                    db.execute('UPDATE Hitters SET HittingTeamId = ? WHERE HittingPlayerId = ?', (team_id, player_id))
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
                # If removing a player, get the current player ID first before updating
                if player_id is None:
                    # Get the player currently in this position before removing
                    previous_player = db.execute(f'SELECT {position} FROM TeamPitchers WHERE PitchingTeamId = ?', (team_id,)).fetchone()
                    previous_player_id = previous_player[0] if previous_player and previous_player[0] is not None else None
                    
                    # Now update the TeamPitchers table
                    db.execute(f'UPDATE TeamPitchers SET {position} = NULL WHERE PitchingTeamId = ?', (team_id,))
                    
                    # If there was a player in this position, update their team reference
                    if previous_player_id is not None:
                        db.execute('UPDATE Pitchers SET PitchingTeamId = NULL WHERE PitchingPlayerId = ?', (previous_player_id,))
                else:
                    db.execute(f'UPDATE TeamPitchers SET {position} = ? WHERE PitchingTeamId = ?', (player_id, team_id))
                    # Update the player's team reference
                    db.execute('UPDATE Pitchers SET PitchingTeamId = ? WHERE PitchingPlayerId = ?', (team_id, player_id))
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
    
@bp.route('/players/<string:player_type>/<int:player_id>', methods=['DELETE'])
def remove_player(player_type, player_id):
    """Remove a player from the available players list by setting the status to 'NA'
    
    Path parameters:
    - player_type: 'hitter' or 'pitcher' (required)
    - player_id: The ID of the player to remove (required)
    """
    try:
        player_type = player_type.lower()

        if player_type not in ['hitter', 'pitcher']:
            return jsonify({'error': 'player_type parameter must be either "hitter" or "pitcher"'}), 400
        
        db = get_db()
        
        if player_type == 'hitter':
            db.execute('UPDATE Hitters SET Status = ? WHERE HittingPlayerId = ?', ('NA', player_id))
        else:
            db.execute('UPDATE Pitchers SET Status = ? WHERE PitchingPlayerId = ?', ('NA', player_id))
            
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'Player {player_id} removed from available players list'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error removing player from available players list: {str(e)}")
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
                AND Status = 'FA'
            '''
            print("Position", position)
            print("Hitter Positions", HITTER_POSITIONS)
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
                for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG', 'SGCalc']:
                    if key in player_dict and player_dict[key] is not None:
                        player_dict[key] = float(player_dict[key])
                result.append(player_dict)
        else:  # pitcher
            query = '''
                SELECT * FROM Pitchers 
                WHERE PitchingTeamId IS NULL
                AND Status = 'FA'
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
                for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9', 'BABIP', 'FIP', 'SGCalc']:
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
                    # Get player details with additional stats
                    player = db.execute('''
                        SELECT HittingPlayerId, PlayerName, Position, Status, 
                               HR, R, RBI, SB, AVG, SGCalc
                        FROM Hitters 
                        WHERE HittingPlayerId = ?
                    ''', (player_id,)).fetchone()
                    if player:
                        player_dict = dict(player)
                        # Convert numeric fields to appropriate Python types
                        for key in ['HR', 'R', 'RBI', 'SB']:
                            if key in player_dict and player_dict[key] is not None:
                                player_dict[key] = int(player_dict[key])
                        for key in ['AVG', 'SGCalc']:
                            if key in player_dict and player_dict[key] is not None:
                                player_dict[key] = float(player_dict[key])
                        hitter_positions[position] = player_dict
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
                    # Get player details with additional stats
                    player = db.execute('''
                        SELECT PitchingPlayerId, PlayerName, Position, Status,
                               W, SO, ERA, WHIP, SVH, SGCalc
                        FROM Pitchers 
                        WHERE PitchingPlayerId = ?
                    ''', (player_id,)).fetchone()
                    if player:
                        player_dict = dict(player)
                        # Convert numeric fields to appropriate Python types
                        for key in ['W', 'SO', 'SVH']:
                            if key in player_dict and player_dict[key] is not None:
                                player_dict[key] = int(player_dict[key])
                        for key in ['ERA', 'WHIP', 'SGCalc']:
                            if key in player_dict and player_dict[key] is not None:
                                player_dict[key] = float(player_dict[key])
                        pitcher_positions[position] = player_dict
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

@bp.route('/calculate-standard-gains', methods=['POST'])
def calculate_standard_gains():
    """Calculate Standard Gains values for all available players based on a team's current stats and a model's thresholds.
    
    This endpoint:
    1. Takes a team ID and model ID as input
    2. Calculates the current team's stats
    3. Gets the model's threshold values
    4. Calculates the gaps between current stats and thresholds
    5. For each available player, calculates how much they would help close those gaps
    6. Updates the SGCalc column in the Hitters and Pitchers tables
    
    Request body:
    {
        "team_id": int,
        "model_id": int
    }
    
    Returns:
    {
        "status": "success",
        "team_stats": { current team stats },
        "gaps": { gaps between current stats and thresholds },
        "top_hitters": [ top 25 hitters by SGCalc ],
        "top_pitchers": [ top 25 pitchers by SGCalc ]
    }
    """
    try:
        data = request.get_json()
        print("DATA", data)
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        team_id = data.get('team_id')
        model_id = data.get('model_id')

        if not team_id or not model_id:
            return jsonify({"error": "Missing required parameters: team_id and model_id"}), 400
        
        # Get current team stats
        team_stats = get_current_team_stats(team_id)
        print("TEAM STATS", team_stats)
        # Get threshold values from the model
        thresholds = get_model_thresholds(model_id)
        print("THRESHOLDS", thresholds)
        # Calculate gaps between current stats and thresholds
        gaps = calculate_category_gaps(team_stats, thresholds)
        print("GAP", gaps)
        # Get available players (not on this team)
        available_hitters = get_available_hitters(team_id)
        available_pitchers = get_available_pitchers(team_id)
        print("AVALABLE PLAYERS RETRIEVED")
        # Calculate SG values for hitters and update database
        for hitter in available_hitters:
            sg_value = calculate_sg_value(hitter, team_stats, gaps, is_hitter=True)
            update_player_sg(hitter["HittingPlayerId"], sg_value, is_hitter=True)
        print("HITTERS COMPLETE")
        # Calculate SG values for pitchers and update database
        for pitcher in available_pitchers:
            sg_value = calculate_sg_value(pitcher, team_stats, gaps, is_hitter=False)
            update_player_sg(pitcher["PitchingPlayerId"], sg_value, is_hitter=False)
        print("PITCHERS COMPLETE")
        # Get top players by SGCalc
        top_hitters = get_top_players_by_sg(is_hitter=True, limit=25)
        top_pitchers = get_top_players_by_sg(is_hitter=False, limit=25)
        print("TOP PLAYERS RETRIEVED", top_hitters, top_pitchers)
        return jsonify({
            "status": "success",
            "team_stats": team_stats,
            "gaps": gaps,
            "top_hitters": top_hitters,
            "top_pitchers": top_pitchers
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_current_team_stats(team_id):
    """Get the current statistics for a team.
    
    This combines hitting and pitching stats into a single dictionary.
    """
    try:
        db = get_db()
        
        # Check if team exists
        team = db.execute('SELECT TeamId, TeamName, Owner FROM Teams WHERE TeamId = ?', (team_id,)).fetchone()
        if not team:
            raise ValueError(f'No team found with TeamId {team_id}')
        
        # Initialize stats dictionary
        team_stats = {
            "R": 0, "HR": 0, "RBI": 0, "SB": 0, "AVG": 0,  # Hitting stats
            "W": 0, "K": 0, "ERA": 0, "WHIP": 0, "SVH": 0  # Pitching stats
        }
        
        # Get hitting stats
        hitters = db.execute('''
            SELECT * FROM Hitters
            WHERE HittingTeamId = ?
        ''', (team_id,)).fetchall()
        
        # Calculate raw hitting totals
        total_ab = 0
        total_hits = 0
        
        for hitter in hitters:
            team_stats["R"] += hitter["R"] if hitter["R"] is not None else 0
            team_stats["HR"] += hitter["HR"] if hitter["HR"] is not None else 0
            team_stats["RBI"] += hitter["RBI"] if hitter["RBI"] is not None else 0
            team_stats["SB"] += hitter["SB"] if hitter["SB"] is not None else 0
            
            # For AVG calculation
            ab = hitter["AB"] if hitter["AB"] is not None else 0
            hits = hitter["H"] if hitter["H"] is not None else 0
            total_ab += ab
            total_hits += hits
        
        # Calculate AVG
        team_stats["AVG"] = total_hits / total_ab if total_ab > 0 else 0.0
        
        # Get pitching stats
        pitchers = db.execute('''
            SELECT * FROM Pitchers
            WHERE PitchingTeamId = ?
        ''', (team_id,)).fetchall()
        
        # Calculate raw pitching totals
        total_innings = 0
        total_earned_runs = 0  # For ERA calculation
        total_whip_product = 0  # For WHIP calculation
        
        for pitcher in pitchers:
            team_stats["W"] += pitcher["W"] if pitcher["W"] is not None else 0
            team_stats["K"] += pitcher["SO"] if pitcher["SO"] is not None else 0
            team_stats["SVH"] += pitcher["SVH"] if pitcher["SVH"] is not None else 0
            
            # For ERA and WHIP calculation
            ip = pitcher["IP"] if pitcher["IP"] is not None else 0
            era = pitcher["ERA"] if pitcher["ERA"] is not None else 0
            whip = pitcher["WHIP"] if pitcher["WHIP"] is not None else 0
            
            # Back-calculate earned runs: ER = (ERA * IP) / 9
            earned_runs = (era * ip) / 9
            
            total_innings += ip
            total_earned_runs += earned_runs
            total_whip_product += whip * ip  # For weighted WHIP
        
        # Calculate weighted ERA and WHIP
        if total_innings > 0:
            # ERA = (9 * total_earned_runs) / total_innings
            team_stats["ERA"] = (9 * total_earned_runs) / total_innings
            team_stats["WHIP"] = total_whip_product / total_innings
        
        return team_stats
    except Exception as e:
        print("ERROR", e)
        return None

def calculate_optimized_team_stats(team_id, optimized_hitters=None, optimized_pitchers=None):
    """Calculate optimized team stats based on the current team and the optimized lineup.
    
    Args:
        team_id (int): The team ID
        optimized_hitters (list): List of hitter player IDs in the optimized lineup
        optimized_pitchers (list): List of pitcher player IDs in the optimized lineup
        
    Returns:
        dict: A dictionary containing optimized hitting and pitching stats
    """
    try:
        db = get_db()
        
        # Check if team exists
        team = db.execute('SELECT TeamId, TeamName, Owner FROM Teams WHERE TeamId = ?', (team_id,)).fetchone()
        if not team:
            raise ValueError(f'No team found with TeamId {team_id}')
        
        # Initialize stats dictionaries
        optimized_hitting_stats = {
            "R": 0, "HR": 0, "RBI": 0, "SB": 0, "AVG": 0
        }
        
        optimized_pitching_stats = {
            "W": 0, "K": 0, "ERA": 0, "WHIP": 0, "SVH": 0
        }
        
        # Process hitters if provided
        if optimized_hitters and len(optimized_hitters) > 0:
            # Get current team hitters that are not in the optimized lineup
            current_hitters = db.execute('''
                SELECT * FROM Hitters
                WHERE HittingTeamId = ? AND HittingPlayerId NOT IN ({})
            '''.format(','.join(['?'] * len(optimized_hitters))), 
            (team_id, *optimized_hitters)).fetchall()
            
            # Get the optimized hitters' stats
            optimized_hitter_stats = db.execute('''
                SELECT * FROM Hitters
                WHERE HittingPlayerId IN ({})
            '''.format(','.join(['?'] * len(optimized_hitters))),
            optimized_hitters).fetchall()
            
            # Calculate raw hitting totals
            total_ab = 0
            total_hits = 0
            
            # Add stats from current team hitters not in optimized lineup
            for hitter in current_hitters:
                optimized_hitting_stats["R"] += hitter["R"] if hitter["R"] is not None else 0
                optimized_hitting_stats["HR"] += hitter["HR"] if hitter["HR"] is not None else 0
                optimized_hitting_stats["RBI"] += hitter["RBI"] if hitter["RBI"] is not None else 0
                optimized_hitting_stats["SB"] += hitter["SB"] if hitter["SB"] is not None else 0
                
                # For AVG calculation
                ab = hitter["AB"] if hitter["AB"] is not None else 0
                hits = hitter["H"] if hitter["H"] is not None else 0
                total_ab += ab
                total_hits += hits
            
            # Add stats from optimized hitters
            for hitter in optimized_hitter_stats:
                optimized_hitting_stats["R"] += hitter["R"] if hitter["R"] is not None else 0
                optimized_hitting_stats["HR"] += hitter["HR"] if hitter["HR"] is not None else 0
                optimized_hitting_stats["RBI"] += hitter["RBI"] if hitter["RBI"] is not None else 0
                optimized_hitting_stats["SB"] += hitter["SB"] if hitter["SB"] is not None else 0
                
                # For AVG calculation
                ab = hitter["AB"] if hitter["AB"] is not None else 0
                hits = hitter["H"] if hitter["H"] is not None else 0
                total_ab += ab
                total_hits += hits
            
            # Calculate AVG
            optimized_hitting_stats["AVG"] = total_hits / total_ab if total_ab > 0 else 0.0
        
        # Process pitchers if provided
        if optimized_pitchers and len(optimized_pitchers) > 0:
            # Get current team pitchers that are not in the optimized lineup
            current_pitchers = db.execute('''
                SELECT * FROM Pitchers
                WHERE PitchingTeamId = ? AND PitchingPlayerId NOT IN ({})
            '''.format(','.join(['?'] * len(optimized_pitchers))), 
            (team_id, *optimized_pitchers)).fetchall()
            
            # Get the optimized pitchers' stats
            optimized_pitcher_stats = db.execute('''
                SELECT * FROM Pitchers
                WHERE PitchingPlayerId IN ({})
            '''.format(','.join(['?'] * len(optimized_pitchers))),
            optimized_pitchers).fetchall()
            
            # Calculate raw pitching totals
            total_innings = 0
            total_earned_runs = 0  # For ERA calculation
            total_whip_product = 0  # For WHIP calculation
            
            # Add stats from current team pitchers not in optimized lineup
            for pitcher in current_pitchers:
                optimized_pitching_stats["W"] += pitcher["W"] if pitcher["W"] is not None else 0
                optimized_pitching_stats["K"] += pitcher["SO"] if pitcher["SO"] is not None else 0
                optimized_pitching_stats["SVH"] += pitcher["SVH"] if pitcher["SVH"] is not None else 0
                
                # For ERA and WHIP calculation
                ip = pitcher["IP"] if pitcher["IP"] is not None else 0
                era = pitcher["ERA"] if pitcher["ERA"] is not None else 0
                whip = pitcher["WHIP"] if pitcher["WHIP"] is not None else 0
                
                # Back-calculate earned runs: ER = (ERA * IP) / 9
                earned_runs = (era * ip) / 9
                
                total_innings += ip
                total_earned_runs += earned_runs
                total_whip_product += whip * ip  # For weighted WHIP
            
            # Add stats from optimized pitchers
            for pitcher in optimized_pitcher_stats:
                optimized_pitching_stats["W"] += pitcher["W"] if pitcher["W"] is not None else 0
                optimized_pitching_stats["K"] += pitcher["SO"] if pitcher["SO"] is not None else 0
                optimized_pitching_stats["SVH"] += pitcher["SVH"] if pitcher["SVH"] is not None else 0
                
                # For ERA and WHIP calculation
                ip = pitcher["IP"] if pitcher["IP"] is not None else 0
                era = pitcher["ERA"] if pitcher["ERA"] is not None else 0
                whip = pitcher["WHIP"] if pitcher["WHIP"] is not None else 0
                
                # Back-calculate earned runs: ER = (ERA * IP) / 9
                earned_runs = (era * ip) / 9
                
                total_innings += ip
                total_earned_runs += earned_runs
                total_whip_product += whip * ip  # For weighted WHIP
            
            # Calculate weighted ERA and WHIP
            if total_innings > 0:
                # ERA = (9 * total_earned_runs) / total_innings
                optimized_pitching_stats["ERA"] = (9 * total_earned_runs) / total_innings
                optimized_pitching_stats["WHIP"] = total_whip_product / total_innings
        
        return {
            "optimized_hitting_stats": optimized_hitting_stats,
            "optimized_pitching_stats": optimized_pitching_stats
        }
    except Exception as e:
        print("ERROR calculating optimized stats:", e)
        return {
            "optimized_hitting_stats": {},
            "optimized_pitching_stats": {}
        }

def get_model_thresholds(model_id):
    """Get the threshold values from a specific model."""
    db = get_db()
    
    # Get model data from Standings table
    model = db.execute('''
        SELECT ModelId, R, HR, RBI, SB, AVG, W, K, ERA, WHIP, SVH 
        FROM Standings 
        WHERE ModelId = ?
    ''', (model_id,)).fetchone()
    
    if not model:
        raise ValueError(f'No model found with ModelId {model_id}')
    
    # Convert to dictionary
    thresholds = dict(model)
    
    return thresholds

def calculate_category_gaps(team_stats, thresholds):
    """Calculate the gaps between current team stats and model thresholds."""
    gaps = {}
    
    # For counting stats (higher is better)
    for stat in ["R", "HR", "RBI", "SB", "W", "K", "SVH"]:
        gap = thresholds[stat] - team_stats[stat]
        # Ensure at least a small positive value to avoid division by zero
        gaps[stat] = max(gap, 0.1)
    
    # For ratio stats (lower is better for ERA, WHIP)
    gaps["ERA"] = max(team_stats["ERA"] - thresholds["ERA"], 0.1)
    gaps["WHIP"] = max(team_stats["WHIP"] - thresholds["WHIP"], 0.1)
    
    # For AVG (higher is better)
    gaps["AVG"] = max(thresholds["AVG"] - team_stats["AVG"], 0.001)
    
    return gaps

def get_available_hitters(team_id):
    """Get all hitters not on the specified team and with 'FA' status."""
    db = get_db()
    
    hitters = db.execute('''
        SELECT * FROM Hitters
        WHERE (HittingTeamId IS NULL OR HittingTeamId != ?)
        AND Status = 'FA'
    ''', (team_id,)).fetchall()
    
    return [dict(hitter) for hitter in hitters]

def get_available_pitchers(team_id):
    """Get all pitchers not on the specified team and with 'FA' status."""
    db = get_db()
    
    pitchers = db.execute('''
        SELECT * FROM Pitchers
        WHERE (PitchingTeamId IS NULL OR PitchingTeamId != ?)
        AND Status = 'FA'
    ''', (team_id,)).fetchall()
    
    return [dict(pitcher) for pitcher in pitchers]

def calculate_sg_value(player, team_stats, gaps, is_hitter):
    """Calculate the Standard Gains value for a player."""
    # Initialize SG value
    sg_value = 0
    
    if is_hitter:
        # Calculate how much this player helps for each hitting category
        for stat in ["R", "HR", "RBI", "SB"]:
            if gaps[stat] > 0:  # Only count stats where we need improvement
                player_stat = player[stat] if player[stat] is not None else 0
                # Each point of contribution in this category is weighted by how far we are from target
                sg_value += (player_stat / gaps[stat])
        
        # Handle AVG differently (contribution depends on AB)
        if gaps["AVG"] > 0:
            ab = player["AB"] if player["AB"] is not None else 0
            hits = player["H"] if player["H"] is not None else 0
            
            if ab > 0:
                player_avg = hits / ab
                # Player's contribution to team AVG is weighted by their AB
                player_avg_impact = (player_avg - team_stats["AVG"]) * ab
                sg_value += (player_avg_impact / gaps["AVG"])
    else:  # Pitcher
        # Calculate pitching contributions
        for stat in ["W", "K", "SVH"]:
            player_stat = stat if stat != "K" else "SO"
            if gaps[stat] > 0:
                player_stat = player[player_stat] if player[player_stat] is not None else 0
                sg_value += (player_stat / gaps[stat])
        
        # Handle ERA and WHIP (lower is better)
        if gaps["ERA"] > 0:
            ip = player["IP"] if player["IP"] is not None else 0
            era = player["ERA"] if player["ERA"] is not None else 0
            if ip > 0:
                era_impact = (team_stats["ERA"] - era) * ip
                sg_value += (era_impact / gaps["ERA"])
        
        if gaps["WHIP"] > 0:
            ip = player["IP"] if player["IP"] is not None else 0
            whip = player["WHIP"] if player["WHIP"] is not None else 0
            if ip > 0:
                whip_impact = (team_stats["WHIP"] - whip) * ip
                sg_value += (whip_impact / gaps["WHIP"])
    
    # Apply position scarcity multipliers (optional)
    position_multipliers = {
        "C": 1.2,
        "SS": 1.15,
        "2B": 1.1,
        "3B": 1.05,
        "OF": 1.0,
        "1B": 1.0,
        "RP": 1.1,
        "SP": 1.0
    }
    
    if is_hitter and "Position" in player:
        sg_value *= position_multipliers.get(player["Position"], 1.0)
    elif not is_hitter and "Role" in player:
        sg_value *= position_multipliers.get(player["Role"], 1.0)
    
    return sg_value

def update_player_sg(player_id, sg_value, is_hitter):
    """Update the SGCalc value for a player in the database."""
    db = get_db()
    
    if is_hitter:
        db.execute('''
            UPDATE Hitters
            SET SGCalc = ?
            WHERE HittingPlayerId = ?
        ''', (sg_value, player_id))
    else:
        db.execute('''
            UPDATE Pitchers
            SET SGCalc = ?
            WHERE PitchingPlayerId = ?
        ''', (sg_value, player_id))
    
    db.commit()

def get_top_players_by_sg(is_hitter, limit=25):
    """Get the top players by SGCalc value."""
    db = get_db()
    
    if is_hitter:
        players = db.execute('''
            SELECT * FROM Hitters
            WHERE SGCalc IS NOT NULL AND Status = 'FA'
            ORDER BY SGCalc DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        
        # Convert to list of dictionaries with proper types
        result = []
        for player in players:
            player_dict = dict(player)
            # Convert numeric fields to appropriate Python types
            for key in ['Age', 'G', 'PA', 'AB', 'H', 'HR', 'R', 'RBI', 'BB', 'HBP', 'SB']:
                if key in player_dict and player_dict[key] is not None:
                    player_dict[key] = int(player_dict[key])
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG', 'SGCalc']:
                if key in player_dict and player_dict[key] is not None:
                    player_dict[key] = float(player_dict[key])
            result.append(player_dict)
        
        return result
    else:
        players = db.execute('''
            SELECT * FROM Pitchers
            WHERE SGCalc IS NOT NULL AND Status = 'FA'
            ORDER BY SGCalc DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        
        # Convert to list of dictionaries with proper types
        result = []
        for player in players:
            player_dict = dict(player)
            # Convert numeric fields to appropriate Python types
            for key in ['Age', 'W', 'QS', 'G', 'SV', 'HLD', 'SVH', 'IP', 'SO']:
                if key in player_dict and player_dict[key] is not None:
                    player_dict[key] = int(player_dict[key])
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9', 'BABIP', 'FIP', 'SGCalc']:
                if key in player_dict and player_dict[key] is not None:
                    player_dict[key] = float(player_dict[key])
            result.append(player_dict)
        
        return result

@bp.route('/top-hitters', methods=['GET'])
def get_top_hitters():
    """Get top hitters by SG value."""
    try:
        # Get limit from query parameter, default to 25
        limit = request.args.get('limit', default=25, type=int)
        
        # Get model_id from query parameter, default to 1
        model_id = request.args.get('model_id', default=1, type=int)
        
        # Get top hitters
        hitters = get_top_players_by_sg(is_hitter=True, limit=limit)
        
        # Return response
        result = {
            'model_id': model_id,
            'hitters': hitters
        }
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error retrieving top hitters: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/top-pitchers', methods=['GET'])
def get_top_pitchers():
    """Get top pitchers by SG value."""
    try:
        # Get limit from query parameter, default to 25
        limit = request.args.get('limit', default=25, type=int)
        
        # Get model_id from query parameter, default to 1
        model_id = request.args.get('model_id', default=1, type=int)
        
        # Get top pitchers
        pitchers = get_top_players_by_sg(is_hitter=False, limit=limit)
        
        # Return response
        result = {
            'model_id': model_id,
            'pitchers': pitchers
        }
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error retrieving top pitchers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/top-players', methods=['GET'])
def get_top_players():
    """Get top hitters and pitchers by SG value."""
    try:
        # Get limit from query parameter, default to 25
        limit = request.args.get('limit', default=25, type=int)
        
        # Get model_id from query parameter, default to 1
        model_id = request.args.get('model_id', default=1, type=int)
        
        # Get top hitters and pitchers
        hitters = get_top_players_by_sg(is_hitter=True, limit=limit)
        pitchers = get_top_players_by_sg(is_hitter=False, limit=limit)
        
        # Return response
        result = {
            'model_id': model_id,
            'hitters': hitters,
            'pitchers': pitchers
        }
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error retrieving top players: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/gethitterstats/<int:player_id>', methods=['GET'])
def get_hitter_stats(player_id):
    """Get stats for a specific hitter."""
    try:
        db = get_db()
        
        # Get hitter data
        hitter = db.execute('''
            SELECT * FROM Hitters
            WHERE HittingPlayerId = ?
        ''', (player_id,)).fetchone()
        
        if not hitter:
            return jsonify({'error': f'Hitter with ID {player_id} not found'}), 404
        
        # Convert to dictionary with proper types
        hitter_dict = dict(hitter)
        
        # Convert numeric fields to appropriate Python types
        for key in ['Age', 'G', 'PA', 'AB', 'H', 'HR', 'R', 'RBI', 'BB', 'HBP', 'SB']:
            if key in hitter_dict and hitter_dict[key] is not None:
                hitter_dict[key] = int(hitter_dict[key])
        for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG', 'SGCalc']:
            if key in hitter_dict and hitter_dict[key] is not None:
                hitter_dict[key] = float(hitter_dict[key])
        
        return jsonify(hitter_dict)
    except Exception as e:
        current_app.logger.error(f"Error retrieving hitter stats for player with ID {player_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/getpitcherstats/<int:player_id>', methods=['GET'])
def get_pitcher_stats(player_id):
    """Get stats for a specific pitcher."""
    try:
        db = get_db()
        
        # Get pitcher data
        pitcher = db.execute('''
            SELECT * FROM Pitchers
            WHERE PitchingPlayerId = ?
        ''', (player_id,)).fetchone()
        
        if not pitcher:
            return jsonify({'error': f'Pitcher with ID {player_id} not found'}), 404
        
        # Convert to dictionary with proper types
        pitcher_dict = dict(pitcher)
        
        # Convert numeric fields to appropriate Python types
        for key in ['Age', 'W', 'QS', 'G', 'SV', 'HLD', 'SVH', 'IP', 'SO']:
            if key in pitcher_dict and pitcher_dict[key] is not None:
                pitcher_dict[key] = int(pitcher_dict[key])
        for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9', 'BABIP', 'FIP', 'SGCalc']:
            if key in pitcher_dict and pitcher_dict[key] is not None:
                pitcher_dict[key] = float(pitcher_dict[key])
        
        return jsonify(pitcher_dict)
    except Exception as e:
        current_app.logger.error(f"Error retrieving pitcher stats for player with ID {player_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/generate-optimal-lineup', methods=['POST'])
def generate_optimal_lineup():
    """Generate an optimal lineup using linear programming.
    
    This endpoint:
    1. Takes budget constraints, team ID, model ID, and roster requirements as input
    2. Uses linear programming to find the optimal lineup that maximizes standard gains
       while respecting budget and roster position constraints
    
    Request body:
    {
        "team_id": int,          # Team ID to identify the existing roster/team context
        "model_id": int,         # Model ID for standard gains calculation
        "budget": float,         # Total budget constraint (e.g., $100)
        "lineup_type": string,   # "hitting", "pitching", or "both"
        "bench_positions": int   # Number of bench positions to account for (applies to hitters in "both" mode)
    }
    
    Returns:
    {
        "status": "success",
        "optimal_lineup": [
            {
                "player_id": int,
                "name": string,
                "position": string,
                "salary": float,
                "sg_value": float
            },
            ...
        ],
        "total_cost": float,
        "total_sg_value": float
    }
    """
    try:
        # Get request data
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['team_id', 'model_id', 'budget', 'lineup_type', 'bench_positions']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        team_id = data['team_id']
        model_id = data['model_id']
        budget = float(data['budget'])
        lineup_type = data['lineup_type'].lower()
        bench_positions = int(data['bench_positions'])
        
        # Validate lineup_type
        if lineup_type not in ['hitting', 'pitching', 'both']:
            return jsonify({'error': 'lineup_type must be either "hitting", "pitching", or "both"'}), 400
        
        # Check if the team exists
        db = get_db()
        team = db.execute(
            'SELECT TeamId, TeamName, Owner, Salary FROM Teams WHERE TeamId = ?',
            (team_id,)
        ).fetchone()
        
        if not team:
            return jsonify({'error': f'No team found with TeamId {team_id}'}), 404
        
        # For "both" option, we'll handle hitters and pitchers separately and then combine the results
        if lineup_type == 'both':
            # Total bench positions is hardcoded to 3, with the remainder allocated to pitchers
            TOTAL_BENCH_POSITIONS = 3
            hitter_bench_positions = bench_positions
            pitcher_bench_positions = TOTAL_BENCH_POSITIONS - hitter_bench_positions
            
            # Determine required positions for hitters
            hitter_positions = []
            team_hitters = db.execute('SELECT * FROM TeamHitters WHERE HittingTeamId = ?', (team_id,)).fetchone()
            
            if team_hitters:
                team_hitters_dict = dict(team_hitters)
                # Find empty positions
                for position in HITTER_POSITIONS:
                    if position in team_hitters_dict and not team_hitters_dict[position]:
                        # Only include bench positions up to the specified number
                        if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= hitter_bench_positions):
                            hitter_positions.append(position)
            else:
                # If no team hitters record exists, all positions are required
                # Only include bench positions up to the specified number
                for position in HITTER_POSITIONS:
                    if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= hitter_bench_positions):
                        hitter_positions.append(position)
            
            # Determine required positions for pitchers
            pitcher_positions = []
            team_pitchers = db.execute('SELECT * FROM TeamPitchers WHERE PitchingTeamId = ?', (team_id,)).fetchone()
            
            if team_pitchers:
                team_pitchers_dict = dict(team_pitchers)
                # Find empty positions
                for position in PITCHER_POSITIONS:
                    if position in team_pitchers_dict and not team_pitchers_dict[position]:
                        # Only include bench positions up to the specified number
                        if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= pitcher_bench_positions):
                            pitcher_positions.append(position)
            else:
                # If no team pitchers record exists, all positions are required
                # Only include bench positions up to the specified number
                for position in PITCHER_POSITIONS:
                    if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= pitcher_bench_positions):
                        pitcher_positions.append(position)
            
            # If no positions need to be filled, return early
            if not hitter_positions and not pitcher_positions:
                return jsonify({
                    'status': 'success',
                    'message': 'No positions need to be filled.',
                    'optimal_lineup': []
                })
            
            # Get available players
            available_hitters = get_available_hitters(team_id)
            available_pitchers = get_available_pitchers(team_id)
            
            # Get team stats and model thresholds for SG calculation
            team_stats = get_current_team_stats(team_id)
            thresholds = get_model_thresholds(model_id)
            gaps = calculate_category_gaps(team_stats, thresholds)
            
            # Calculate SG values for available hitters
            for player in available_hitters:
                sg_value = calculate_sg_value(player, team_stats, gaps, is_hitter=True)
                if 'SGCalc' not in player or player['SGCalc'] is None:
                    update_player_sg(player['HittingPlayerId'], sg_value, is_hitter=True)
                    player['SGCalc'] = sg_value
            
            # Calculate SG values for available pitchers
            for player in available_pitchers:
                sg_value = calculate_sg_value(player, team_stats, gaps, is_hitter=False)
                if 'SGCalc' not in player or player['SGCalc'] is None:
                    update_player_sg(player['PitchingPlayerId'], sg_value, is_hitter=False)
                    player['SGCalc'] = sg_value
            
            # Import PuLP for linear programming
            import pulp
            
            # Create a linear programming problem
            prob = pulp.LpProblem("OptimalLineup", pulp.LpMaximize)
            
            # Create decision variables for each player-position combination
            player_vars = {}
            
            # Create variables for each valid hitter-position combination
            for player in available_hitters:
                player_id = player['HittingPlayerId']
                player_position = player['Position']
                
                for position in hitter_positions:
                    # Check if player can play this position
                    position_requirements = POSITION_MAPPING.get(position, [])
                    
                    if player_position in position_requirements:
                        var_name = f"hitter_{player_id}_pos_{position}"
                        player_vars[(player_id, position, 'hitting')] = pulp.LpVariable(var_name, 0, 1, pulp.LpBinary)
            
            # Create variables for each valid pitcher-position combination
            for player in available_pitchers:
                player_id = player['PitchingPlayerId']
                
                for position in pitcher_positions:
                    var_name = f"pitcher_{player_id}_pos_{position}"
                    player_vars[(player_id, position, 'pitching')] = pulp.LpVariable(var_name, 0, 1, pulp.LpBinary)
            
            # Objective function: Maximize total SG value
            prob += pulp.lpSum([player_vars.get((player['HittingPlayerId'], position, 'hitting'), 0) * player.get('SGCalc', 0) 
                               for player in available_hitters for position in hitter_positions]) + \
                   pulp.lpSum([player_vars.get((player['PitchingPlayerId'], position, 'pitching'), 0) * player.get('SGCalc', 0) 
                               for player in available_pitchers for position in pitcher_positions])
            
            # Constraint 1: Budget constraint (combined for both hitters and pitchers)
            prob += pulp.lpSum([player_vars.get((player['HittingPlayerId'], position, 'hitting'), 0) * player.get('AdjustedSalary', 0) 
                               for player in available_hitters for position in hitter_positions]) + \
                   pulp.lpSum([player_vars.get((player['PitchingPlayerId'], position, 'pitching'), 0) * player.get('AdjustedSalary', 0) 
                               for player in available_pitchers for position in pitcher_positions]) <= budget
            
            # Constraint 2: Each hitter position must be filled by exactly one player
            for position in hitter_positions:
                prob += pulp.lpSum([player_vars.get((player['HittingPlayerId'], position, 'hitting'), 0) 
                                   for player in available_hitters]) == 1
            
            # Constraint 3: Each pitcher position must be filled by exactly one player
            for position in pitcher_positions:
                prob += pulp.lpSum([player_vars.get((player['PitchingPlayerId'], position, 'pitching'), 0) 
                                   for player in available_pitchers]) == 1
            
            # Constraint 4: Each hitter can be assigned to at most one position
            for player in available_hitters:
                player_id = player['HittingPlayerId']
                prob += pulp.lpSum([player_vars.get((player_id, position, 'hitting'), 0) 
                                   for position in hitter_positions]) <= 1
            
            # Constraint 5: Each pitcher can be assigned to at most one position
            for player in available_pitchers:
                player_id = player['PitchingPlayerId']
                prob += pulp.lpSum([player_vars.get((player_id, position, 'pitching'), 0) 
                                   for position in pitcher_positions]) <= 1
            
            # Solve the problem with a timeout
            solver = pulp.PULP_CBC_CMD(timeLimit=30)  # 30-second timeout
            prob.solve(solver)
            
            # Check if a solution was found
            if pulp.LpStatus[prob.status] != 'Optimal':
                return jsonify({
                    'status': 'error',
                    'message': f'No optimal solution found. Status: {pulp.LpStatus[prob.status]}',
                    'hitter_positions': hitter_positions,
                    'pitcher_positions': pitcher_positions
                }), 400
            
            # Extract the optimal lineup
            optimal_lineup = []
            total_cost = 0
            total_sg_value = 0
            
            # Extract hitters
            for player in available_hitters:
                player_id = player['HittingPlayerId']
                for position in hitter_positions:
                    var = player_vars.get((player_id, position, 'hitting'))
                    if var and var.value() == 1:
                        player_salary = player.get('AdjustedSalary', 0)
                        player_sg = player.get('SGCalc', 0)
                        
                        optimal_lineup.append({
                            'player_id': player_id,
                            'name': player.get('PlayerName', 'Unknown'),
                            'position': position,
                            'original_position': player.get('Position', 'Unknown'),
                            'salary': player_salary,
                            'sg_value': player_sg,
                            'type': 'hitting'
                        })
                        
                        total_cost += player_salary
                        total_sg_value += player_sg
            
            # Extract pitchers
            for player in available_pitchers:
                player_id = player['PitchingPlayerId']
                for position in pitcher_positions:
                    var = player_vars.get((player_id, position, 'pitching'))
                    if var and var.value() == 1:
                        player_salary = player.get('AdjustedSalary', 0)
                        player_sg = player.get('SGCalc', 0)
                        
                        optimal_lineup.append({
                            'player_id': player_id,
                            'name': player.get('PlayerName', 'Unknown'),
                            'position': position,
                            'original_position': player.get('Position', 'Unknown'),
                            'salary': player_salary,
                            'sg_value': player_sg,
                            'type': 'pitching'
                        })
                        
                        total_cost += player_salary
                        total_sg_value += player_sg
            
            # Sort the lineup by position type (hitters first, then pitchers) and then by position
            hitter_position_order = {pos: idx for idx, pos in enumerate(HITTER_POSITIONS)}
            pitcher_position_order = {pos: idx for idx, pos in enumerate(PITCHER_POSITIONS)}
            
            def sort_key(player):
                if player['type'] == 'hitting':
                    return (0, hitter_position_order.get(player['position'], 999))
                else:
                    return (1, pitcher_position_order.get(player['position'], 999))
            
            optimal_lineup.sort(key=sort_key)
            
            # Extract player IDs from the optimal lineup for stats calculation
            optimized_hitter_ids = []
            optimized_pitcher_ids = []
            
            for player in optimal_lineup:
                if player['type'] == 'hitting':
                    optimized_hitter_ids.append(player['player_id'])
                elif player['type'] == 'pitching':
                    optimized_pitcher_ids.append(player['player_id'])
            
            # Calculate optimized stats
            optimized_stats = calculate_optimized_team_stats(
                team_id, 
                optimized_hitters=optimized_hitter_ids,
                optimized_pitchers=optimized_pitcher_ids
            )
            
            return jsonify({
                'status': 'success',
                'message': 'Optimal lineup generated successfully.',
                'optimal_lineup': optimal_lineup,
                'total_cost': total_cost,
                'total_sg_value': total_sg_value,
                'hitter_positions': hitter_positions,
                'pitcher_positions': pitcher_positions,
                'optimized_hitting_stats': optimized_stats['optimized_hitting_stats'],
                'optimized_pitching_stats': optimized_stats['optimized_pitching_stats']
            })
        
        # Original implementation for 'hitting' or 'pitching' only
        # Determine required positions based on lineup_type
        required_positions = []
        
        if lineup_type == 'hitting':
            # Get current hitter positions
            team_hitters = db.execute('SELECT * FROM TeamHitters WHERE HittingTeamId = ?', (team_id,)).fetchone()
            
            if team_hitters:
                team_hitters_dict = dict(team_hitters)
                # Find empty positions
                for position in HITTER_POSITIONS:
                    if position in team_hitters_dict and not team_hitters_dict[position]:
                        # Only include bench positions up to the specified number
                        if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= bench_positions):
                            required_positions.append(position)
            else:
                # If no team hitters record exists, all positions are required
                # Only include bench positions up to the specified number
                for position in HITTER_POSITIONS:
                    if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= bench_positions):
                        required_positions.append(position)
        
        else:  # lineup_type == 'pitching'
            # Get current pitcher positions
            team_pitchers = db.execute('SELECT * FROM TeamPitchers WHERE PitchingTeamId = ?', (team_id,)).fetchone()
            
            if team_pitchers:
                team_pitchers_dict = dict(team_pitchers)
                # Find empty positions
                for position in PITCHER_POSITIONS:
                    if position in team_pitchers_dict and not team_pitchers_dict[position]:
                        # Only include bench positions up to the specified number
                        if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= bench_positions):
                            required_positions.append(position)
            else:
                # If no team pitchers record exists, all positions are required
                # Only include bench positions up to the specified number
                for position in PITCHER_POSITIONS:
                    if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= bench_positions):
                        required_positions.append(position)
        
        # If no positions need to be filled, return early
        if not required_positions:
            return jsonify({
                'status': 'success',
                'message': 'No positions need to be filled.',
                'optimal_lineup': []
            })
        
        # Get available players based on lineup_type
        available_players = []
        if lineup_type == 'hitting':
            # Get available hitters
            available_players = get_available_hitters(team_id)
        else:  # lineup_type == 'pitching'
            # Get available pitchers
            available_players = get_available_pitchers(team_id)
        
        # Get team stats and model thresholds for SG calculation
        team_stats = get_current_team_stats(team_id)
        thresholds = get_model_thresholds(model_id)
        gaps = calculate_category_gaps(team_stats, thresholds)
        
        # Calculate SG values for available players
        for player in available_players:
            is_hitter = lineup_type == 'hitting'
            sg_value = calculate_sg_value(player, team_stats, gaps, is_hitter=is_hitter)
            
            # Add SG value to player dict if not already present
            if is_hitter:
                player_id_key = 'HittingPlayerId'
                if 'SGCalc' not in player or player['SGCalc'] is None:
                    update_player_sg(player[player_id_key], sg_value, is_hitter=True)
                    player['SGCalc'] = sg_value
            else:
                player_id_key = 'PitchingPlayerId'
                if 'SGCalc' not in player or player['SGCalc'] is None:
                    update_player_sg(player[player_id_key], sg_value, is_hitter=False)
                    player['SGCalc'] = sg_value
        
        # Import PuLP for linear programming
        import pulp
        
        # Create a linear programming problem
        prob = pulp.LpProblem("OptimalLineup", pulp.LpMaximize)
        
        # Create decision variables for each player-position combination
        # 1 if player i is assigned to position j, 0 otherwise
        player_vars = {}
        
        # Determine player ID key based on lineup type
        player_id_key = 'HittingPlayerId' if lineup_type == 'hitting' else 'PitchingPlayerId'
        
        # Create variables for each valid player-position combination
        for player in available_players:
            player_id = player[player_id_key]
            player_position = player['Position']
            
            for position in required_positions:
                # Check if player can play this position
                position_requirements = POSITION_MAPPING.get(position, [])
                
                # For pitchers, all pitchers can play any pitcher position
                if lineup_type == 'pitching' or player_position in position_requirements:
                    var_name = f"player_{player_id}_pos_{position}"
                    player_vars[(player_id, position)] = pulp.LpVariable(var_name, 0, 1, pulp.LpBinary)
        
        # Objective function: Maximize total SG value
        prob += pulp.lpSum([player_vars.get((player[player_id_key], position), 0) * player.get('SGCalc', 0) 
                           for player in available_players for position in required_positions])
        
        # Constraint 1: Budget constraint
        prob += pulp.lpSum([player_vars.get((player[player_id_key], position), 0) * player.get('AdjustedSalary', 0) 
                           for player in available_players for position in required_positions]) <= budget
        
        # Constraint 2: Each position must be filled by exactly one player
        for position in required_positions:
            prob += pulp.lpSum([player_vars.get((player[player_id_key], position), 0) 
                               for player in available_players]) == 1
        
        # Constraint 3: Each player can be assigned to at most one position
        for player in available_players:
            player_id = player[player_id_key]
            prob += pulp.lpSum([player_vars.get((player_id, position), 0) 
                               for position in required_positions]) <= 1
        
        # Solve the problem with a timeout
        solver = pulp.PULP_CBC_CMD(timeLimit=30)  # 30-second timeout
        prob.solve(solver)
        
        # Check if a solution was found
        if pulp.LpStatus[prob.status] != 'Optimal':
            return jsonify({
                'status': 'error',
                'message': f'No optimal solution found. Status: {pulp.LpStatus[prob.status]}',
                'required_positions': required_positions
            }), 400
        
        # Extract the optimal lineup
        optimal_lineup = []
        total_cost = 0
        total_sg_value = 0
        
        for player in available_players:
            player_id = player[player_id_key]
            for position in required_positions:
                var = player_vars.get((player_id, position))
                if var and var.value() == 1:
                    player_salary = player.get('AdjustedSalary', 0)
                    player_sg = player.get('SGCalc', 0)
                    
                    optimal_lineup.append({
                        'player_id': player_id,
                        'name': player.get('PlayerName', 'Unknown'),
                        'position': position,
                        'original_position': player.get('Position', 'Unknown'),
                        'salary': player_salary,
                        'sg_value': player_sg,
                        'type': lineup_type
                    })
                    
                    total_cost += player_salary
                    total_sg_value += player_sg
        
        # Sort the lineup by position
        if lineup_type == 'hitting':
            position_order = {pos: idx for idx, pos in enumerate(HITTER_POSITIONS)}
        else:
            position_order = {pos: idx for idx, pos in enumerate(PITCHER_POSITIONS)}
        
        optimal_lineup.sort(key=lambda x: position_order.get(x['position'], 999))
        
        # Extract player IDs from the optimal lineup for stats calculation
        optimized_hitter_ids = []
        optimized_pitcher_ids = []
        
        for player in optimal_lineup:
            if player['type'] == 'hitting':
                optimized_hitter_ids.append(player['player_id'])
            elif player['type'] == 'pitching':
                optimized_pitcher_ids.append(player['player_id'])
        
        # Calculate optimized stats
        optimized_stats = calculate_optimized_team_stats(
            team_id, 
            optimized_hitters=optimized_hitter_ids if lineup_type in ['hitting', 'both'] else None,
            optimized_pitchers=optimized_pitcher_ids if lineup_type in ['pitching', 'both'] else None
        )
        print("OPTIMIZSED_STATS", optimized_stats)
        return jsonify({
            'status': 'success',
            'message': 'Optimal lineup generated successfully.',
            'optimal_lineup': optimal_lineup,
            'total_cost': total_cost,
            'total_sg_value': total_sg_value,
            'required_positions': required_positions,
            'optimized_hitting_stats': optimized_stats['optimized_hitting_stats'] if lineup_type in ['hitting', 'both'] else {},
            'optimized_pitching_stats': optimized_stats['optimized_pitching_stats'] if lineup_type in ['pitching', 'both'] else {}
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generating optimal lineup: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Helper function to determine required positions
def get_required_positions(team_id, lineup_type, bench_positions):
    """Determine the required positions to fill based on lineup type and bench positions."""
    db = get_db()
    required_positions = []
    
    if lineup_type == 'hitting':
        # Get current hitter positions
        team_hitters = db.execute('SELECT * FROM TeamHitters WHERE HittingTeamId = ?', (team_id,)).fetchone()
        
        if team_hitters:
            team_hitters_dict = dict(team_hitters)
            # Find empty positions
            for position in HITTER_POSITIONS:
                if position in team_hitters_dict and not team_hitters_dict[position]:
                    # Only include bench positions up to the specified number
                    if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= bench_positions):
                        required_positions.append(position)
        else:
            # If no team hitters record exists, all positions are required
            # Only include bench positions up to the specified number
            for position in HITTER_POSITIONS:
                if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= bench_positions):
                    required_positions.append(position)
    
    else:  # lineup_type == 'pitching'
        # Get current pitcher positions
        team_pitchers = db.execute('SELECT * FROM TeamPitchers WHERE PitchingTeamId = ?', (team_id,)).fetchone()
        
        if team_pitchers:
            team_pitchers_dict = dict(team_pitchers)
            # Find empty positions
            for position in PITCHER_POSITIONS:
                if position in team_pitchers_dict and not team_pitchers_dict[position]:
                    # Only include bench positions up to the specified number
                    if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= bench_positions):
                        required_positions.append(position)
        else:
            # If no team pitchers record exists, all positions are required
            # Only include bench positions up to the specified number
            for position in PITCHER_POSITIONS:
                if not position.startswith('Bench') or (position.startswith('Bench') and int(position[5:]) <= bench_positions):
                    required_positions.append(position)
    
    return required_positions

@bp.route('/players/free-agent-hitters', methods=['GET'])
def get_free_agent_hitters():
    """Get all hitters with a status of 'FA'.
    
    Returns a list of all hitters that have a 'FA' status, regardless of team assignment.
    """
    try:
        db = get_db()
        
        query = '''
            SELECT * FROM Hitters 
            WHERE Status = 'NA'
        '''
        
        hitters = db.execute(query).fetchall()
        
        # Convert to list of dictionaries and ensure numeric values are Python native types
        result = []
        for player in hitters:
            player_dict = dict(player)
            # Convert numeric fields to appropriate Python types
            for key in ['Age', 'G', 'PA', 'AB', 'H', 'HR', 'R', 'RBI', 'BB', 'HBP', 'SB']:
                if key in player_dict and player_dict[key] is not None:
                    player_dict[key] = int(player_dict[key])
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'AVG', 'SGCalc']:
                if key in player_dict and player_dict[key] is not None:
                    player_dict[key] = float(player_dict[key])
            result.append(player_dict)
            
        return jsonify({
            'hitters': result
        })
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving free agent hitters: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/players/free-agent-pitchers', methods=['GET'])
def get_free_agent_pitchers():
    """Get all pitchers with a status of 'FA'.
    
    Returns a list of all pitchers that have a 'FA' status, regardless of team assignment.
    """
    try:
        db = get_db()
        
        query = '''
            SELECT * FROM Pitchers 
            WHERE Status = 'NA'
        '''
        
        pitchers = db.execute(query).fetchall()
        
        # Convert to list of dictionaries and ensure numeric values are Python native types
        result = []
        for player in pitchers:
            player_dict = dict(player)
            # Convert numeric fields to appropriate Python types
            for key in ['Age', 'W', 'QS', 'G', 'SV', 'HLD', 'SVH', 'IP', 'SO']:
                if key in player_dict and player_dict[key] is not None:
                    player_dict[key] = int(player_dict[key])
            for key in ['OriginalSalary', 'AdjustedSalary', 'AuctionSalary', 'ERA', 'WHIP', 'K_9', 'BB_9', 'BABIP', 'FIP', 'SGCalc']:
                if key in player_dict and player_dict[key] is not None:
                    player_dict[key] = float(player_dict[key])
            result.append(player_dict)
            
        return jsonify({
            'pitchers': result
        })
        
    except Exception as e:
        current_app.logger.error(f"Error retrieving free agent pitchers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/players/<string:player_type>/<int:player_id>/set-free-agent', methods=['PUT'])
def set_player_as_free_agent(player_type, player_id):
    """Update a player's status to 'FA'.
    
    Path parameters:
    - player_type: 'hitter' or 'pitcher' (required)
    - player_id: The ID of the player to update (required)
    """
    try:
        player_type = player_type.lower()

        if player_type not in ['hitter', 'pitcher']:
            return jsonify({'error': 'player_type parameter must be either "hitter" or "pitcher"'}), 400
        
        db = get_db()
        
        if player_type == 'hitter':
            # Update the player's status to 'FA' and remove team assignment
            db.execute('UPDATE Hitters SET Status = ?, HittingTeamId = NULL WHERE HittingPlayerId = ?', 
                      ('FA', player_id))
        else:
            # Update the player's status to 'FA' and remove team assignment
            db.execute('UPDATE Pitchers SET Status = ?, PitchingTeamId = NULL WHERE PitchingPlayerId = ?', 
                      ('FA', player_id))
            
        db.commit()
        
        return jsonify({
            'success': True,
            'message': f'{player_type.capitalize()} with ID {player_id} has been set as a free agent'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error setting player as free agent: {str(e)}")
        return jsonify({'error': str(e)}), 500