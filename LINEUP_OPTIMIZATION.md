# Lineup Optimization with PuLP

This document explains how the lineup optimization function works in the Fantasy Baseball backend application, focusing on the use of linear programming with PuLP to find the optimal lineup.

## What is PuLP?

[PuLP](https://coin-or.github.io/pulp/) is an open-source linear programming (LP) modeler written in Python. It allows you to create mathematical optimization models where:

- You have an objective function to maximize or minimize
- Subject to a set of constraints
- With decision variables that can take on specific values

PuLP is particularly useful for solving problems like:
- Resource allocation
- Scheduling
- Portfolio optimization
- And in our case: optimal lineup selection

## How the Lineup Optimization Works

The `/api/generate-optimal-lineup` endpoint uses linear programming to find the best possible lineup given:
- A budget constraint
- Required roster positions
- Player statistics and their impact on team performance

### Key Components of the Implementation

#### 1. Decision Variables

The core of the optimization is a set of binary decision variables that represent whether a player is assigned to a specific position:

```python
player_vars[(player_id, position)] = pulp.LpVariable(var_name, 0, 1, pulp.LpBinary)
```

Each variable can be either 0 (player not assigned to position) or 1 (player assigned to position).

#### 2. Objective Function

The goal is to maximize the total Standard Gains (SG) value of the lineup:

```python
prob += pulp.lpSum([player_vars.get((player[player_id_key], position), 0) * player.get('SGCalc', 0) 
                   for player in available_players for position in required_positions])
```

This sums the SG value of each player multiplied by whether they're selected for a position (0 or 1).

#### 3. Constraints

The optimization is subject to several constraints:

**Budget Constraint**: The total cost of selected players must not exceed the budget.
```python
prob += pulp.lpSum([player_vars.get((player[player_id_key], position), 0) * player.get('AdjustedSalary', 0) 
                   for player in available_players for position in required_positions]) <= budget
```

**Position Filling Constraint**: Each required position must be filled by exactly one player.
```python
for position in required_positions:
    prob += pulp.lpSum([player_vars.get((player[player_id_key], position), 0) 
                       for player in available_players]) == 1
```

**Player Assignment Constraint**: Each player can be assigned to at most one position.
```python
for player in available_players:
    player_id = player[player_id_key]
    prob += pulp.lpSum([player_vars.get((player_id, position), 0) 
                       for position in required_positions]) <= 1
```

**Position Eligibility**: Players can only be assigned to positions they're eligible for.
```python
position_requirements = POSITION_MAPPING.get(position, [])
if lineup_type == 'pitching' or player_position in position_requirements:
    # Create variable only if player is eligible for this position
```

#### 4. Solving the Problem

The optimization problem is solved using the CBC (COIN-OR Branch and Cut) solver with a timeout:

```python
solver = pulp.PULP_CBC_CMD(timeLimit=30)  # 30-second timeout
prob.solve(solver)
```

#### 5. Extracting the Results

After solving, the function extracts the optimal lineup by checking which decision variables have a value of 1:

```python
for player in available_players:
    player_id = player[player_id_key]
    for position in required_positions:
        var = player_vars.get((player_id, position))
        if var and var.value() == 1:
            # This player is part of the optimal lineup
```

## Position Mapping

The application uses position mapping to determine which players are eligible for which roster spots:

```python
POSITION_MAPPING = {
    'C': ['C'],
    'FirstBase': ['1B'],
    'SecondBase': ['2B'],
    'ShortStop': ['SS'],
    'ThirdBase': ['3B'],
    'MiddleInfielder': ['2B', 'SS'],
    'CornerInfielder': ['1B', '3B'],
    'Outfield1': ['OF'],
    # ... and so on
}
```

This allows for flexible position eligibility, such as a player who can play both 2B and SS being eligible for the MiddleInfielder position.

## Standard Gains Calculation

The optimization relies on Standard Gains (SG) values, which measure how much a player contributes to improving team statistics relative to a benchmark model. These values are calculated by:

1. Determining the current team's statistical gaps compared to a benchmark model
2. Calculating how each player's statistics would help close those gaps
3. Weighting the contributions across different statistical categories

## Handling Different Lineup Types

The function supports three lineup types:
- `hitting`: Optimizes only the hitting lineup
- `pitching`: Optimizes only the pitching lineup
- `both`: Optimizes both hitting and pitching lineups simultaneously

For the `both` option, the function:
1. Determines required positions for both hitters and pitchers
2. Creates separate decision variables for each
3. Combines them in a single optimization problem with a shared budget constraint
4. Returns a combined optimal lineup

## Importing PuLP

Currently, PuLP is imported inside the function:

```python
# Import PuLP for linear programming
import pulp
```

This is not ideal for several reasons:
1. It adds overhead each time the function is called
2. It makes the dependency less explicit
3. It's not consistent with Python best practices

**Recommendation**: Move the import to the top of the file with other imports:

```python
from flask import Blueprint, request, jsonify, current_app
import json
import numpy as np
import pandas as pd
import pulp  # Add this import at the top
```

## Performance Considerations

The function includes a timeout parameter (`timeLimit=30`) to prevent the solver from running too long on complex problems. This is important because:

1. Linear programming can be computationally intensive
2. As the number of players and positions increases, the problem complexity grows
3. Web requests should complete in a reasonable time

## Conclusion

The lineup optimization function uses linear programming through PuLP to find the best possible lineup given budget constraints and roster requirements. It maximizes the total Standard Gains value while ensuring all positions are filled with eligible players and staying within budget.

This approach is much more powerful than simple sorting or greedy algorithms because it considers all constraints simultaneously and finds the globally optimal solution. 