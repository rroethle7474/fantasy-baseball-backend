import pandas as pd
import numpy as np
from app.database.db import get_db

def analyze_data(model_id):
    """Analyze data for a specific model and store results.
    
    This function:
    1. Retrieves team and statistics data from the database
    2. Separates playoff vs non-playoff teams
    3. Calculates mean, median, and standard deviation for each statistical category
    4. Identifies minimum and maximum values for each category among playoff teams
    5. Calculates correlations between different statistical categories
    6. Stores analysis results in the database
    
    Args:
        model_id: ID of the model to analyze
        
    Returns:
        Dictionary containing benchmarks and correlations
    """
    # Get data from database
    db = get_db()
    
    # Get all teams for this model
    teams = db.execute(
        '''
        SELECT t.id, t.team_name, t.season_year, t.made_playoffs, t.wins, t.losses, t.ties
        FROM teams t
        WHERE t.model_id = ?
        ''',
        (model_id,)
    ).fetchall()
    
    # Get all statistics for these teams
    team_stats = {}
    for team in teams:
        stats = db.execute(
            '''
            SELECT category, value
            FROM statistics
            WHERE team_id = ?
            ''',
            (team['id'],)
        ).fetchall()
        
        team_stats[team['id']] = {
            'team_data': dict(team),
            'stats': {stat['category']: stat['value'] for stat in stats}
        }
    
    # Convert to DataFrame for analysis
    data = []
    for team_id, team_info in team_stats.items():
        row = {
            'team_id': team_id,
            'team_name': team_info['team_data']['team_name'],
            'season_year': team_info['team_data']['season_year'],
            'made_playoffs': team_info['team_data']['made_playoffs'],
            'wins': team_info['team_data']['wins'],
            'losses': team_info['team_data']['losses'],
            'ties': team_info['team_data']['ties']
        }
        row.update(team_info['stats'])
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Calculate benchmarks
    categories = ['HR', 'RBI', 'R', 'SB', 'AVG', 'ERA', 'WHIP', 'W', 'SV_H', 'K']
    
    # Separate playoff vs non-playoff teams
    playoff_teams = df[df['made_playoffs'] == 1]
    non_playoff_teams = df[df['made_playoffs'] == 0]
    
    # Check if we have playoff teams to analyze
    if len(playoff_teams) == 0:
        raise ValueError("No playoff teams found in the dataset. Cannot calculate benchmarks.")
    
    benchmarks = {}
    for category in categories:
        if category in df.columns:
            # For pitching stats (ERA, WHIP), lower is better
            if category in ['ERA', 'WHIP']:
                benchmarks[category] = {
                    'mean_value': float(playoff_teams[category].mean()),
                    'median_value': float(playoff_teams[category].median()),
                    'std_dev': float(playoff_teams[category].std()),
                    'min_value': float(playoff_teams[category].min()),  # Best value for pitching stats
                    'max_value': float(playoff_teams[category].max())
                }
            else:
                # For batting stats, higher is better
                benchmarks[category] = {
                    'mean_value': float(playoff_teams[category].mean()),
                    'median_value': float(playoff_teams[category].median()),
                    'std_dev': float(playoff_teams[category].std()),
                    'min_value': float(playoff_teams[category].min()),
                    'max_value': float(playoff_teams[category].max())  # Best value for batting stats
                }
    
    # Calculate correlations between categories
    valid_categories = [cat for cat in categories if cat in df.columns]
    correlation_matrix = df[valid_categories].corr()
    correlations = []
    
    for i, cat1 in enumerate(valid_categories):
        for j, cat2 in enumerate(valid_categories):
            if i < j:  # Only store each pair once
                correlations.append({
                    'category1': cat1,
                    'category2': cat2,
                    'coefficient': float(correlation_matrix.loc[cat1, cat2])
                })
    
    # Store benchmarks in database
    for category, values in benchmarks.items():
        db.execute(
            '''
            INSERT INTO benchmarks (model_id, category, mean_value, median_value, std_dev, min_value, max_value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                model_id, 
                category, 
                values['mean_value'], 
                values['median_value'], 
                values['std_dev'],
                values['min_value'],
                values['max_value']
            )
        )
    
    # Store correlations in database
    for corr in correlations:
        db.execute(
            '''
            INSERT INTO correlations (model_id, category1, category2, coefficient)
            VALUES (?, ?, ?, ?)
            ''',
            (model_id, corr['category1'], corr['category2'], corr['coefficient'])
        )
    
    db.commit()
    
    return {
        'benchmarks': benchmarks,
        'correlations': correlations
    }

def calculate_what_if(model_id, adjustments):
    """Calculate what-if scenario based on adjusted values.
    
    Args:
        model_id: ID of the model to use for calculations
        adjustments: Dictionary of category adjustments
        
    Returns:
        Dictionary of adjusted values for all categories
    """
    db = get_db()
    
    # Get correlation data
    correlations = db.execute(
        'SELECT category1, category2, coefficient FROM correlations WHERE model_id = ?',
        (model_id,)
    ).fetchall()
    
    correlation_dict = {}
    for corr in correlations:
        if corr['category1'] not in correlation_dict:
            correlation_dict[corr['category1']] = {}
        if corr['category2'] not in correlation_dict:
            correlation_dict[corr['category2']] = {}
        
        correlation_dict[corr['category1']][corr['category2']] = float(corr['coefficient'])
        correlation_dict[corr['category2']][corr['category1']] = float(corr['coefficient'])
    
    # Get benchmark data
    benchmarks = db.execute(
        'SELECT category, mean_value FROM benchmarks WHERE model_id = ?',
        (model_id,)
    ).fetchall()
    
    benchmark_dict = {b['category']: float(b['mean_value']) for b in benchmarks}
    
    # Calculate adjusted values
    results = benchmark_dict.copy()
    
    # Update with user adjustments
    for category, value in adjustments.items():
        results[category] = float(value)
    
    # Calculate related adjustments
    for adj_category in adjustments:
        delta_percent = (float(adjustments[adj_category]) - benchmark_dict[adj_category]) / benchmark_dict[adj_category]
        
        for related_category, coeff in correlation_dict.get(adj_category, {}).items():
            if related_category not in adjustments:  # Don't adjust categories the user explicitly set
                impact = delta_percent * coeff
                results[related_category] = float(benchmark_dict[related_category] * (1 + impact))
    
    # Ensure all values are Python native types
    return {k: float(v) for k, v in results.items()}