# JCL Fantasy Baseball Backend

This repository contains the backend implementation for the JCL Fantasy Baseball 2025 auction system. The application is built with Flask and provides various APIs for fantasy baseball team optimization, standard gains calculation, and player analysis.

## Getting Started

### Prerequisites

- Python 3.8+
- pip (Python package manager)
- virtualenv (Python virtual environment)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/JCL-Auction-2025.git
cd fantasy-baseball-backend
```

2. Set up and activate the virtual environment:
```bash
# Create a virtual environment in the jcl-2025-backend directory
python -m venv jcl-2025-backend

# Activate the virtual environment
# On Windows:
./jcl-2025-backend/Scripts/activate
# On Unix or MacOS:
source jcl-2025-backend/bin/activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

Note: The `jcl-2025-backend` virtual environment folder is excluded in `.gitignore` to keep the repository clean and ensure that:
- IDE indexing remains efficient
- Virtual environment files are not tracked in version control
- Each developer can maintain their own isolated environment

Remember to always activate the virtual environment before running the application or installing new packages.

### Running the Application

To start the application, run:
```bash
python run.py
```

The server will start on `http://localhost:5000` by default.

## Key Features

- Standard Gains Calculation
- Player Impact Analysis
- Optimal Lineup Generation using Linear Programming
- Database integration for player statistics

## API Routes

The application provides the following key API endpoints:

### Standard Gains Calculation

```
POST /api/calculate-standard-gains
```
Calculates standard gains values for all available players based on the selected model and team roster.

**Request Body:**
```json
{
  "modelId": 1,  // 1 for 25th Percentile, 2 for Playoff Averages
  "teamId": 123  // ID of the team to analyze
}
```

### Player Impact Analysis

```
GET /api/player-impact/:playerId
```
Analyzes how a specific player would impact the team's statistics.

### Optimal Lineup Generation

```
POST /api/generate-optimal-lineup
```
Generates an optimal lineup based on budget constraints, selected model, and roster requirements.

**Request Body:**
```json
{
  "budget": 260,
  "modelId": 1,
  "rosterRequirements": {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "OF": 5,
    "UTIL": 1,
    "MI": 1,
    "CI": 1,
    "SP": 9,
    "Bench": 3
  }
}
```

## Database

The application uses a SQLite database (located in the `instance` directory) with the following main tables:

- **Hitters**: Contains batting statistics with an added `SGCalc` column for standard gains calculation
- **Pitchers**: Contains pitching statistics with an added `SGCalc` column for standard gains calculation
- **Teams**: Stores information about fantasy teams
- **Rosters**: Tracks which players are on which teams

## Packages Used

The application relies on the following key packages:

- **Flask (3.1.0)**: Web framework for building the API
- **Flask-CORS (5.0.1)**: Cross-Origin Resource Sharing support
- **Pandas (2.2.3)**: Data manipulation and analysis
- **NumPy (2.2.3)**: Numerical computing
- **PuLP (3.0.2)**: Linear programming solver for optimization
- **SciPy (1.15.2)**: Scientific computing
- **Requests (2.32.3)**: HTTP library

For a complete list of dependencies, see `requirements.txt`.

## Project Structure

```
fantasy-baseball-backend/
├── app/                  # Main application package
│   ├── __init__.py       # Application factory
│   ├── models/           # Database models
│   ├── routes/           # API routes
│   └── services/         # Business logic
├── instance/             # Instance-specific data (database)
├── hitting_files/        # Hitting statistics data
├── pitching_files/       # Pitching statistics data
├── run.py                # Application entry point
└── requirements.txt      # Package dependencies
```

## Additional Documentation

For more detailed information, refer to:
- `API_DOCUMENTATION.md`: Complete API documentation
- `standard-gains-calculation-guide.md`: Guide to understanding standard gains calculation
- `fantasy-baseball-implementation-tasks.md`: Implementation tasks and roadmap 