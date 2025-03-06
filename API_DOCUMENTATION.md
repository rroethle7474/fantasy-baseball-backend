# Fantasy Baseball API Documentation

This document provides comprehensive documentation for the Fantasy Baseball API endpoints.

## Table of Contents

1. [Standings](#standings)
2. [Teams](#teams)
3. [Roster Management](#roster-management)
4. [Players](#players)
5. [Statistics](#statistics)
6. [Models and Analysis](#models-and-analysis)

---

## Standings

### Get All Standings

Retrieves all records from the Standings table.

- **URL**: `/api/standings`
- **Method**: `GET`
- **URL Parameters**: None
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "standings": [
        {
          "ModelId": 1,
          "Description": "2023 Season",
          "R": 800,
          "HR": 200,
          "RBI": 750,
          "SB": 100,
          "AVG": 0.275,
          "W": 95,
          "K": 1500,
          "ERA": 3.50,
          "WHIP": 1.15,
          "SVH": 120
        },
        ...
      ]
    }
    ```
- **Error Response**:
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Get Specific Standing

Retrieves a specific standing by its ModelId.

- **URL**: `/api/standings/:model_id`
- **Method**: `GET`
- **URL Parameters**:
  - `model_id`: ID of the model to retrieve
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "ModelId": 1,
      "Description": "2023 Season",
      "R": 800,
      "HR": 200,
      "RBI": 750,
      "SB": 100,
      "AVG": 0.275,
      "W": 95,
      "K": 1500,
      "ERA": 3.50,
      "WHIP": 1.15,
      "SVH": 120
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No standing found with ModelId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

---

## Teams

### Get All Teams

Retrieves all teams with basic information.

- **URL**: `/api/teams`
- **Method**: `GET`
- **URL Parameters**: None
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "teams": [
        {
          "TeamId": 1,
          "TeamName": "Team A",
          "Owner": "Owner A",
          "Salary": 260.0
        },
        ...
      ]
    }
    ```
- **Error Response**:
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Get Specific Team

Retrieves a specific team by its TeamId.

- **URL**: `/api/teams/:team_id`
- **Method**: `GET`
- **URL Parameters**:
  - `team_id`: ID of the team to retrieve
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "TeamId": 1,
      "TeamName": "Team A",
      "Owner": "Owner A",
      "Salary": 260.0
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Get Team Roster

Retrieves a team's complete roster including hitters and pitchers.

- **URL**: `/api/teams/:team_id/roster`
- **Method**: `GET`
- **URL Parameters**:
  - `team_id`: ID of the team to retrieve roster for
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "team": {
        "TeamId": 1,
        "TeamName": "Team A",
        "Owner": "Owner A",
        "Salary": 260.0
      },
      "hitters": [
        {
          "HittingPlayerId": 1,
          "PlayerName": "Player A",
          "Team": "MLB Team A",
          "Position": "SS,OF",
          "Status": "Active",
          "Age": 27,
          "HittingTeamId": 1,
          "OriginalSalary": 35.0,
          "AdjustedSalary": 35.0,
          "AuctionSalary": 37.0,
          "G": 150,
          "PA": 600,
          "AB": 550,
          "H": 165,
          "HR": 30,
          "R": 100,
          "RBI": 95,
          "BB": 45,
          "HBP": 5,
          "SB": 15,
          "AVG": 0.300
        },
        ...
      ],
      "pitchers": [
        {
          "PitchingPlayerId": 1,
          "PlayerName": "Pitcher A",
          "Team": "MLB Team B",
          "Position": "SP",
          "Status": "Active",
          "Age": 29,
          "PitchingTeamId": 1,
          "OriginalSalary": 40.0,
          "AdjustedSalary": 40.0,
          "AuctionSalary": 42.0,
          "W": 15,
          "QS": 20,
          "ERA": 3.20,
          "WHIP": 1.05,
          "G": 32,
          "SV": 0,
          "HLD": 0,
          "SVH": 0,
          "IP": 200,
          "SO": 220,
          "K_9": 9.9,
          "BB_9": 2.1,
          "BABIP": .256,
          "FIP": 3.76
        },
        ...
      ]
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Get Team Hitters

Retrieves all hitters for a specific team.

- **URL**: `/api/teams/:team_id/hitters`
- **Method**: `GET`
- **URL Parameters**:
  - `team_id`: ID of the team to retrieve hitters for
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "team": {
        "TeamId": 1,
        "TeamName": "Team A",
        "Owner": "Owner A",
        "Salary": 260.0
      },
      "hitters": [
        {
          "HittingPlayerId": 1,
          "PlayerName": "Player A",
          "Team": "MLB Team A",
          "Position": "SS,OF",
          "Status": "Active",
          "Age": 27,
          "HittingTeamId": 1,
          "OriginalSalary": 35.0,
          "AdjustedSalary": 35.0,
          "AuctionSalary": 37.0,
          "G": 150,
          "PA": 600,
          "AB": 550,
          "H": 165,
          "HR": 30,
          "R": 100,
          "RBI": 95,
          "BB": 45,
          "HBP": 5,
          "SB": 15,
          "AVG": 0.300
        },
        ...
      ]
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Get Team Pitchers

Retrieves all pitchers for a specific team.

- **URL**: `/api/teams/:team_id/pitchers`
- **Method**: `GET`
- **URL Parameters**:
  - `team_id`: ID of the team to retrieve pitchers for
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "team": {
        "TeamId": 1,
        "TeamName": "Team A",
        "Owner": "Owner A",
        "Salary": 260.0
      },
      "pitchers": [
        {
          "PitchingPlayerId": 1,
          "PlayerName": "Pitcher A",
          "Team": "MLB Team B",
          "Position": "SP",
          "Status": "Active",
          "Age": 29,
          "PitchingTeamId": 1,
          "OriginalSalary": 40.0,
          "AdjustedSalary": 40.0,
          "AuctionSalary": 42.0,
          "W": 15,
          "QS": 20,
          "ERA": 3.20,
          "WHIP": 1.05,
          "G": 32,
          "SV": 0,
          "HLD": 0,
          "SVH": 0,
          "IP": 200,
          "SO": 220,
          "K_9": 9.9,
          "BB_9": 2.1,
          "BABIP": .234,
          "FIP": 3.67
        },
        ...
      ]
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

---

## Roster Management

### Get Team Roster Structure

Retrieves the current roster structure for a team, showing which positions are filled and which are empty.

- **URL**: `/api/teams/:team_id/roster/structure`
- **Method**: `GET`
- **URL Parameters**:
  - `team_id`: ID of the team to retrieve roster structure for
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "team": {
        "TeamId": 1,
        "TeamName": "Team A",
        "Owner": "Owner A",
        "Salary": 260.0
      },
      "hitter_positions": {
        "C": {
          "HittingPlayerId": 1,
          "PlayerName": "Catcher A",
          "Position": "C",
          "Status": "Active"
        },
        "FirstBase": null,
        "SecondBase": {
          "HittingPlayerId": 2,
          "PlayerName": "Second Baseman A",
          "Position": "2B",
          "Status": "Active"
        },
        ...
      },
      "pitcher_positions": {
        "Pitcher1": {
          "PitchingPlayerId": 1,
          "PlayerName": "Pitcher A",
          "Position": "SP",
          "Status": "Active"
        },
        "Pitcher2": null,
        ...
      }
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Update Team Roster

Updates a team's roster by adding, removing, or changing a player at a specific position.

- **URL**: `/api/teams/:team_id/roster/update`
- **Method**: `POST`
- **URL Parameters**:
  - `team_id`: ID of the team to update roster for
- **Query Parameters**: None
- **Request Body**:
  ```json
  {
    "player_type": "hitter",  // or "pitcher"
    "position": "C",          // from HITTER_POSITIONS or PITCHER_POSITIONS
    "player_id": 1            // ID of player to assign, or null to remove
  }
  ```
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "success": true,
      "message": "Updated hitter position C for team 1"
    }
    ```
- **Error Response**:
  - **Code**: 400
  - **Content**: `{ "error": "No data provided" }`
  - **Code**: 400
  - **Content**: `{ "error": "Missing required fields: player_type, position" }`
  - **Code**: 400
  - **Content**: `{ "error": "player_type must be either 'hitter' or 'pitcher'" }`
  - **Code**: 400
  - **Content**: `{ "error": "Invalid position for hitter. Must be one of: C, FirstBase, ..." }`
  - **Code**: 400
  - **Content**: `{ "error": "Player with HittingPlayerId 1 is not eligible for position C" }`
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 404
  - **Content**: `{ "error": "No hitter found with HittingPlayerId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

---

## Players

### Get Available Players

Retrieves players that are not assigned to any team.

- **URL**: `/api/players/available`
- **Method**: `GET`
- **URL Parameters**: None
- **Query Parameters**:
  - `player_type`: Type of player to retrieve (`hitter` or `pitcher`) - **Required**
  - `position`: Filter by position (optional) - For hitters, this is the roster position (e.g., 'C', 'FirstBase', etc.)
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "player_type": "hitter",
      "position": "C",
      "players": [
        {
          "HittingPlayerId": 1,
          "PlayerName": "Player A",
          "Team": "MLB Team A",
          "Position": "C",
          "Status": "Active",
          "Age": 27,
          "HittingTeamId": null,
          "OriginalSalary": 35.0,
          "AdjustedSalary": 35.0,
          "AuctionSalary": 37.0,
          "G": 150,
          "PA": 600,
          "AB": 550,
          "H": 165,
          "HR": 30,
          "R": 100,
          "RBI": 95,
          "BB": 45,
          "HBP": 5,
          "SB": 15,
          "AVG": 0.300
        },
        ...
      ]
    }
    ```
- **Error Response**:
  - **Code**: 400
  - **Content**: `{ "error": "player_type parameter is required and must be either 'hitter' or 'pitcher'" }`
  - **Code**: 400
  - **Content**: `{ "error": "Invalid hitter position. Must be one of: C, FirstBase, ..." }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

---

## Statistics

### Get Team Hitting Stats

Calculates and returns aggregate hitting statistics for a team.

- **URL**: `/api/teams/:team_id/stats/hitting`
- **Method**: `GET`
- **URL Parameters**:
  - `team_id`: ID of the team to retrieve stats for
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "team": {
        "TeamId": 1,
        "TeamName": "Team A",
        "Owner": "Owner A"
      },
      "stats": {
        "R": 800,
        "HR": 200,
        "RBI": 750,
        "SB": 100,
        "AVG": 0.275
      }
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Get Team Pitching Stats

Calculates and returns aggregate pitching statistics for a team.

- **URL**: `/api/teams/:team_id/stats/pitching`
- **Method**: `GET`
- **URL Parameters**:
  - `team_id`: ID of the team to retrieve stats for
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "team": {
        "TeamId": 1,
        "TeamName": "Team A",
        "Owner": "Owner A"
      },
      "stats": {
        "W": 95,
        "K": 1500,
        "SVH": 120,
        "ERA": 3.50,
        "WHIP": 1.15
      }
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Get All Team Stats

Calculates and returns all aggregate statistics (hitting and pitching) for a team.

- **URL**: `/api/teams/:team_id/stats`
- **Method**: `GET`
- **URL Parameters**:
  - `team_id`: ID of the team to retrieve stats for
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "team": {
        "TeamId": 1,
        "TeamName": "Team A",
        "Owner": "Owner A"
      },
      "hitting_stats": {
        "R": 800,
        "HR": 200,
        "RBI": 750,
        "SB": 100,
        "AVG": 0.275
      },
      "pitching_stats": {
        "W": 95,
        "K": 1500,
        "SVH": 120,
        "ERA": 3.50,
        "WHIP": 1.15
      }
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No team found with TeamId 1" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

---

## Models and Analysis

### Get Models

Retrieves a list of all analysis models.

- **URL**: `/api/models`
- **Method**: `GET`
- **URL Parameters**: None
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "models": [
        {
          "id": 1,
          "name": "2023 Season",
          "description": "Analysis of 2023 season data",
          "created_timestamp": "2023-12-01T12:00:00"
        },
        ...
      ]
    }
    ```
- **Error Response**:
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Delete Model

Deletes a specific model and its associated data.

- **URL**: `/api/models/:model_id`
- **Method**: `DELETE`
- **URL Parameters**:
  - `model_id`: ID of the model to delete
- **Query Parameters**: None
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "success": true
    }
    ```
- **Error Response**:
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Get Benchmarks

Retrieves benchmark data for a specific model.

- **URL**: `/api/benchmarks`
- **Method**: `GET`
- **URL Parameters**: None
- **Query Parameters**:
  - `model_id`: ID of the model to retrieve benchmarks for (optional, defaults to latest model)
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "model_id": 1,
      "benchmarks": [
        {
          "category": "HR",
          "mean_value": 25.5,
          "median_value": 23.0,
          "std_dev": 10.2,
          "min_value": 0.0,
          "max_value": 60.0
        },
        ...
      ],
      "correlations": [
        {
          "category1": "HR",
          "category2": "RBI",
          "coefficient": 0.85
        },
        ...
      ]
    }
    ```
- **Error Response**:
  - **Code**: 404
  - **Content**: `{ "error": "No models found" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Calculate What-If Scenario

Calculates what-if scenario based on adjusted values.

- **URL**: `/api/what-if`
- **Method**: `POST`
- **URL Parameters**: None
- **Query Parameters**: None
- **Request Body**:
  ```json
  {
    "model_id": 1,
    "adjustments": {
      "HR": 30,
      "RBI": 100,
      ...
    }
  }
  ```
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "model_id": 1,
      "results": {
        "playoff_probability": 0.85,
        "win_probability": 0.65,
        ...
      }
    }
    ```
- **Error Response**:
  - **Code**: 400
  - **Content**: `{ "error": "Invalid request data" }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

### Upload Data

Uploads and processes CSV file for analysis.

- **URL**: `/api/upload`
- **Method**: `POST`
- **URL Parameters**: None
- **Query Parameters**: None
- **Request Body**: Form data with:
  - `file`: CSV file to upload
  - `name`: Name of the model (optional)
  - `description`: Description of the model (optional)
- **Success Response**:
  - **Code**: 200
  - **Content**:
    ```json
    {
      "success": true,
      "model_id": 1,
      "summary": {
        "teams": 30,
        "seasons": 1,
        "playoff_teams": 10,
        "non_playoff_teams": 20,
        "categories_analyzed": 10,
        "benchmarks_generated": 10,
        "correlations_calculated": 45
      }
    }
    ```
- **Error Response**:
  - **Code**: 400
  - **Content**: `{ "error": "No file part" }`
  - **Code**: 400
  - **Content**: `{ "error": "No selected file" }`
  - **Code**: 400
  - **Content**: `{ "error": "File must be a CSV" }`
  - **Code**: 400
  - **Content**: `{ "error": "Missing required columns: team_name, season_year, ..." }`
  - **Code**: 400
  - **Content**: `{ "error": "The CSV file is empty" }`
  - **Code**: 400
  - **Content**: `{ "error": "Could not parse the CSV file. Please check the format." }`
  - **Code**: 500
  - **Content**: `{ "error": "Error message" }`

---

## Position Constants

### Hitter Positions

Valid position names for TeamHitters table:

```
'C', 'FirstBase', 'SecondBase', 'ShortStop', 'ThirdBase', 
'MiddleInfielder', 'CornerInfielder', 'Outfield1', 'Outfield2', 
'Outfield3', 'Outfield4', 'Outfield5', 'Utility', 
'Bench1', 'Bench2', 'Bench3'
```

### Pitcher Positions

Valid position names for TeamPitchers table:

```
'Pitcher1', 'Pitcher2', 'Pitcher3', 'Pitcher4', 'Pitcher5',
'Pitcher6', 'Pitcher7', 'Pitcher8', 'Pitcher9',
'Bench1', 'Bench2', 'Bench3'
```

### Position Mapping

Mapping of roster positions to actual player positions:

```
'C': ['C']
'FirstBase': ['1B']
'SecondBase': ['2B']
'ShortStop': ['SS']
'ThirdBase': ['3B']
'MiddleInfielder': ['2B', 'SS']
'CornerInfielder': ['1B', '3B']
'Outfield1': ['OF']
'Outfield2': ['OF']
'Outfield3': ['OF']
'Outfield4': ['OF']
'Outfield5': ['OF']
'Utility': ['C', '1B', '2B', 'SS', '3B', 'OF', 'DH']  # Any position
'Bench1': ['C', '1B', '2B', 'SS', '3B', 'OF', 'DH']   # Any position
'Bench2': ['C', '1B', '2B', 'SS', '3B', 'OF', 'DH']   # Any position
'Bench3': ['C', '1B', '2B', 'SS', '3B', 'OF', 'DH']   # Any position
``` 