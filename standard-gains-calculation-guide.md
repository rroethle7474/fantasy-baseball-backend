# Standard Gains Calculation Implementation Guide

## What is Standard Gains?

Standard Gains (SG) is a fantasy baseball valuation method that measures how much a player would help your *specific* team improve toward your statistical targets. Unlike general player rankings or projections, Standard Gains is contextual to your current roster's strengths and weaknesses.

The core concept is simple: players who provide stats in categories where your team is deficient are more valuable to you than players who excel in categories where your team is already strong. SG calculation quantifies this by measuring each player's potential contribution relative to the gaps between your current team stats and your target thresholds.

This approach helps you make targeted acquisitions that efficiently move your team toward a balanced, competitive roster across all statistical categories.

## Implementation Guide

### 1. Calculate Current Team Statistics

```python
def get_current_team_stats(team_id):
    # Query your database for all players on the given team
    team_players = get_team_roster(team_id)
    
    # Initialize stats dictionary
    team_stats = {
        "R": 0, "HR": 0, "RBI": 0, "SB": 0, "AVG": 0,  # Hitting stats
        "W": 0, "K": 0, "ERA": 0, "WHIP": 0, "SVH": 0  # Pitching stats
    }
    
    # Calculate raw totals
    total_ab = 0
    total_hits = 0
    total_innings = 0
    
    # Sum up hitting stats
    for hitter in team_players["hitters"]:
        team_stats["R"] += hitter["R"]
        team_stats["HR"] += hitter["HR"]
        team_stats["RBI"] += hitter["RBI"]
        team_stats["SB"] += hitter["SB"]
        total_ab += hitter["AB"]
        total_hits += hitter["H"]
    
    # Calculate AVG
    team_stats["AVG"] = total_hits / total_ab if total_ab > 0 else 0
    
    # Sum up pitching stats
    for pitcher in team_players["pitchers"]:
        team_stats["W"] += pitcher["W"]
        team_stats["K"] += pitcher["K"]
        team_stats["SVH"] += pitcher["SVH"]
        # For ERA and WHIP, need to track innings pitched
        total_innings += pitcher["IP"]
        team_stats["ERA"] += pitcher["ERA"] * pitcher["IP"]
        team_stats["WHIP"] += pitcher["WHIP"] * pitcher["IP"]
    
    # Calculate weighted ERA and WHIP
    if total_innings > 0:
        team_stats["ERA"] /= total_innings
        team_stats["WHIP"] /= total_innings
    
    return team_stats
```

### 2. Get Model Threshold Values

```python
def get_model_thresholds(model_id):
    # Query the Models table for the chosen threshold values
    model = db.query.filter_by(ModelId=model_id).first()
    return {
        "R": model.R,
        "HR": model.HR,
        "RBI": model.RBI,
        "SB": model.SB,
        "AVG": model.AVG,
        "W": model.W,
        "K": model.K,
        "ERA": model.ERA,
        "WHIP": model.WHIP,
        "SVH": model.SVH
    }
```

### 3. Calculate Gaps for Each Category

```python
def calculate_category_gaps(team_stats, model_thresholds):
    gaps = {}
    
    # For counting stats (higher is better)
    for stat in ["R", "HR", "RBI", "SB", "W", "K", "SVH"]:
        gaps[stat] = model_thresholds[stat] - team_stats[stat]
    
    # For ratio stats (lower is better for ERA, WHIP)
    gaps["ERA"] = team_stats["ERA"] - model_thresholds["ERA"]
    gaps["WHIP"] = team_stats["WHIP"] - model_thresholds["WHIP"]
    
    # For AVG (higher is better)
    gaps["AVG"] = model_thresholds["AVG"] - team_stats["AVG"]
    
    return gaps
```

### 4. Calculate Standard Gains for Each Player

```python
def calculate_sg_value(player, team_stats, gaps, is_hitter):
    # Initialize SG value
    sg_value = 0
    
    if is_hitter:
        # Calculate how much this player helps for each hitting category
        for stat in ["R", "HR", "RBI", "SB"]:
            if gaps[stat] > 0:  # Only count stats where we need improvement
                # Each point of contribution in this category is weighted by how far we are from target
                sg_value += (player[stat] / gaps[stat]) if gaps[stat] != 0 else 0
        
        # Handle AVG differently (contribution depends on AB)
        if gaps["AVG"] > 0:
            # Player's contribution to team AVG is weighted by their AB
            player_avg_impact = ((player["H"] / player["AB"]) - team_stats["AVG"]) * player["AB"]
            sg_value += (player_avg_impact / gaps["AVG"]) if gaps["AVG"] != 0 else 0
    else:  # Pitcher
        # Calculate pitching contributions
        for stat in ["W", "K", "SVH"]:
            if gaps[stat] > 0:
                sg_value += (player[stat] / gaps[stat]) if gaps[stat] != 0 else 0
        
        # Handle ERA and WHIP (lower is better)
        if gaps["ERA"] > 0:
            era_impact = (team_stats["ERA"] - player["ERA"]) * player["IP"]
            sg_value += (era_impact / gaps["ERA"]) if gaps["ERA"] != 0 else 0
        
        if gaps["WHIP"] > 0:
            whip_impact = (team_stats["WHIP"] - player["WHIP"]) * player["IP"]
            sg_value += (whip_impact / gaps["WHIP"]) if gaps["WHIP"] != 0 else 0
    
    return sg_value
```

### 5. Update All Players

```python
def update_all_players_sg(team_id, model_id):
    # Get current team stats
    team_stats = get_current_team_stats(team_id)
    
    # Get threshold values
    thresholds = get_model_thresholds(model_id)
    
    # Calculate gaps
    gaps = calculate_category_gaps(team_stats, thresholds)
    
    # Get all available players not on this team
    available_hitters = get_available_hitters(team_id)
    available_pitchers = get_available_pitchers(team_id)
    
    # Calculate and update SG values for hitters
    for hitter in available_hitters:
        sg_value = calculate_sg_value(hitter, team_stats, gaps, is_hitter=True)
        update_player_sg(hitter["gPla"], sg_value)
    
    # Calculate and update SG values for pitchers
    for pitcher in available_pitchers:
        sg_value = calculate_sg_value(pitcher, team_stats, gaps, is_hitter=False)
        update_player_sg(pitcher["gPla"], sg_value)
```

## Special Considerations

### 1. Handling Negative Gaps
If your team is already exceeding the threshold in a category, you might want to set the gap to zero or a small positive number to still give some value to that category.

```python
# In calculate_category_gaps function
for stat in ["R", "HR", "RBI", "SB", "W", "K", "SVH"]:
    gap = model_thresholds[stat] - team_stats[stat]
    gaps[stat] = max(gap, 0.1)  # Ensure at least a small positive value
```

### 2. Weighting Categories
You might want to add weights to different categories based on their relative importance.

```python
# Define category weights
weights = {
    "R": 1.0, "HR": 1.2, "RBI": 1.0, "SB": 1.5, "AVG": 1.3,
    "W": 1.2, "K": 1.0, "ERA": 1.4, "WHIP": 1.4, "SVH": 1.1
}

# Apply weights in calculate_sg_value
sg_value += (player[stat] / gaps[stat] * weights[stat]) if gaps[stat] != 0 else 0
```

### 3. Position Scarcity
Consider adjusting SG values based on position scarcity.

```python
# Position scarcity multipliers
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

# Apply in final calculation
sg_value *= position_multipliers.get(player["Position"], 1.0)
```

### 4. Normalization
You may want to normalize the final SG values to make them more intuitive.

```python
# After calculating all SG values
def normalize_sg_values(players, min_val=0, max_val=10):
    sg_values = [p["SGCalc"] for p in players]
    min_sg = min(sg_values)
    max_sg = max(sg_values)
    
    # Normalize to range [min_val, max_val]
    for player in players:
        normalized_sg = min_val + (player["SGCalc"] - min_sg) * (max_val - min_val) / (max_sg - min_sg)
        player["SGCalc"] = normalized_sg
    
    return players
```

## Putting It All Together

For your endpoint implementation, the flow would be:

```python
@app.route('/api/calculate-standard-gains', methods=['POST'])
def calculate_standard_gains():
    data = request.get_json()
    team_id = data.get('team_id')
    model_id = data.get('model_id')
    
    if not team_id or not model_id:
        return jsonify({"error": "Missing required parameters"}), 400
    
    try:
        # Get current team stats
        team_stats = get_current_team_stats(team_id)
        
        # Get threshold values
        thresholds = get_model_thresholds(model_id)
        
        # Calculate gaps
        gaps = calculate_category_gaps(team_stats, thresholds)
        
        # Get available players
        available_hitters = get_available_hitters(team_id)
        available_pitchers = get_available_pitchers(team_id)
        
        # Calculate SG values
        for hitter in available_hitters:
            sg_value = calculate_sg_value(hitter, team_stats, gaps, is_hitter=True)
            update_player_sg(hitter["gPla"], sg_value)
        
        for pitcher in available_pitchers:
            sg_value = calculate_sg_value(pitcher, team_stats, gaps, is_hitter=False)
            update_player_sg(pitcher["gPla"], sg_value)
        
        # Optional: Return top players
        top_hitters = get_top_players(is_hitter=True, limit=25)
        top_pitchers = get_top_players(is_hitter=False, limit=25)
        
        return jsonify({
            "status": "success",
            "team_stats": team_stats,
            "gaps": gaps,
            "top_hitters": top_hitters,
            "top_pitchers": top_pitchers
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

This implementation provides a comprehensive framework for calculating Standard Gains values tailored to your fantasy baseball team's needs.
