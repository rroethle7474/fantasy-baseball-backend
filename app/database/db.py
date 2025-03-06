import sqlite3
import csv
import os
from flask import Flask, g, current_app

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    
    # Execute schema SQL
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        db.executescript(f.read())
    
    # Execute initial data SQL
    initial_data_path = os.path.join(os.path.dirname(__file__), 'initial_data.sql')
    with open(initial_data_path, 'r') as f:
        db.executescript(f.read())
    
    db.commit()

def import_hitters():
    db = get_db()
    
    csv_path = os.path.join(os.path.dirname(__file__), 'players-hitters.csv')
    with open(csv_path, 'r', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)
        
        for row in csv_reader:
            # Convert empty strings to None
            for key, value in row.items():
                if value == '':
                    row[key] = None
            
            db.execute('''
                INSERT INTO Hitters (
                    PlayerName, Team, Position, Status, Age, 
                    HittingTeamId, OriginalSalary, AdjustedSalary, AuctionSalary,
                    G, PA, AB, H, HR, R, RBI, BB, HBP, SB, AVG
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['Name'], row['Team'], row['Position'], row['Status'], row['Age'],
                row['HittingTeamId'], row['OriginalSalary'], row['AdjustedSalary'], row['AuctionSalary'],
                row['G'], row['PA'], row['AB'], row['H'], row['HR'], row['R'], row['RBI'], 
                row['BB'], row['HBP'], row['SB'], row['AVG']
            ))
    
    db.commit()

def import_pitchers():
    db = get_db()
    
    csv_path = os.path.join(os.path.dirname(__file__), 'players-pitchers.csv')
    with open(csv_path, 'r', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)
        
        for row in csv_reader:
            # Convert empty strings to None
            for key, value in row.items():
                if value == '':
                    row[key] = None
            
            db.execute('''
                INSERT INTO Pitchers (
                    PlayerName, Team, Position, Status, Age, 
                    PitchingTeamId, OriginalSalary, AdjustedSalary, AuctionSalary,
                    W, QS, ERA, WHIP, G, SV, HLD, SVH, IP, SO, K_9, BB_9, BABIP, FIP
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['Name'], row['Team'], row['Position'], row['Status'], row['Age'],
                row['PitchingTeamId'], row['OriginalSalary'], row['AdjustedSalary'], row['AuctionSalary'],
                row['W'], row['QS'], row['ERA'], row['WHIP'], row['G'], row['SV'], row['HLD'], row['SVH'], 
                row['IP'], row['SO'], row['K/9'], row['BB/9'], row.get('BABIP'), row.get('FIP')
            ))
    
    db.commit()

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(import_hitters_command)
    app.cli.add_command(import_pitchers_command)

import click
from flask.cli import with_appcontext

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

@click.command('import-hitters')
@with_appcontext
def import_hitters_command():
    """Import hitters data from CSV."""
    import_hitters()
    click.echo('Imported hitters data.')

@click.command('import-pitchers')
@with_appcontext
def import_pitchers_command():
    """Import pitchers data from CSV."""
    import_pitchers()
    click.echo('Imported pitchers data.')