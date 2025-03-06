import sqlite3
import os
from flask import current_app, g
import click
from flask.cli import with_appcontext

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

def migrate_db():
    """Migrate the database to add new columns to Pitchers table."""
    db = get_db()
    
    # Create a backup of the current data
    db.execute("BEGIN TRANSACTION")
    
    try:
        # Step 1: Backup Pitchers data
        db.execute("CREATE TABLE IF NOT EXISTS Pitchers_backup AS SELECT * FROM Pitchers")
        
        # Step 2: Drop the existing Pitchers table
        db.execute("DROP TABLE IF EXISTS Pitchers")
        
        # Step 3: Create the new Pitchers table with additional columns
        db.execute('''
        CREATE TABLE Pitchers (
            PitchingPlayerId INTEGER PRIMARY KEY,
            PlayerName TEXT NOT NULL,
            Team TEXT,
            Position TEXT,
            Status TEXT,
            Age INTEGER,
            PitchingTeamId INTEGER,
            OriginalSalary REAL,
            AdjustedSalary REAL,
            AuctionSalary REAL,
            W INTEGER,
            QS INTEGER,
            ERA REAL,
            WHIP REAL,
            G INTEGER,
            SV INTEGER,
            HLD INTEGER,
            SVH INTEGER,
            IP INTEGER,
            SO INTEGER,
            K_9 REAL,
            BB_9 REAL,
            BABIP REAL,
            FIP REAL,
            FOREIGN KEY (PitchingTeamId) REFERENCES TeamPitchers (PitchingTeamId)
        )
        ''')
        
        # Step 4: Restore data from backup
        db.execute('''
        INSERT INTO Pitchers (
            PitchingPlayerId, PlayerName, Team, Position, Status, Age, 
            PitchingTeamId, OriginalSalary, AdjustedSalary, AuctionSalary,
            W, QS, ERA, WHIP, G, SV, HLD, SVH, IP, SO, K_9, BB_9
        )
        SELECT 
            PitchingPlayerId, PlayerName, Team, Position, Status, Age, 
            PitchingTeamId, OriginalSalary, AdjustedSalary, AuctionSalary,
            W, QS, ERA, WHIP, G, SV, HLD, SVH, IP, SO, K_9, BB_9
        FROM Pitchers_backup
        ''')
        
        # Step 5: Drop the backup table
        db.execute("DROP TABLE Pitchers_backup")
        
        # Commit the transaction
        db.execute("COMMIT")
        
    except Exception as e:
        # Rollback in case of error
        db.execute("ROLLBACK")
        raise e

@click.command('migrate-db')
@with_appcontext
def migrate_db_command():
    """Migrate the database to add new columns."""
    migrate_db()
    click.echo('Database migration completed successfully.')

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(migrate_db_command) 