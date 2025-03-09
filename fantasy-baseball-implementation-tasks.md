# Fantasy Baseball Optimization Implementation Tasks

## Backend Tasks (Python Flask)

### Database Updates (Completed)
- Add `SGCalc` column to Hitters table
- Add `SGCalc` column to Pitchers table

### API Endpoints

#### Standard Gains Calculation
- [ ] Create endpoint `/api/calculate-standard-gains`
  - Input: 
    - Selected model ID (1 for 25th Percentile or 2 for Playoff Averages)
    - Team ID (to identify which roster to analyze)
  - Process: Calculate current roster stats for the specified team, compare to model thresholds, determine gaps
  - Output: Updated SGCalc values for all available players

#### Player Impact Analysis
- [ ] Create endpoint `/api/player-impact/:playerId`
  - Input: Player ID and current roster composition
  - Process: Calculate how this specific player would impact team stats
  - Output: Before/after comparison of team stats with this player added

#### Optimal Lineup Generation
- [ ] Create endpoint `/api/generate-optimal-lineup`
  - Input: Budget constraint, selected model ID, roster construction requirements
  - Process: Implement Linear Programming optimization
  - Output: Optimal player set within budget constraints

### Linear Programming Implementation
- [ ] Install necessary libraries (`pip install pulp scipy pandas`)
- [ ] Define constraint matrices for:
  - Budget limitations
  - Roster position requirements
  - Statistical threshold targets
- [ ] Implement objective function to maximize statistical gains
- [ ] Add solve function with timeout parameter for large dataset handling

## Frontend Tasks (React + Tailwind)

### UI Components

#### Model Selection
- [ ] Create dropdown component for selecting threshold model (25th Percentile or Playoff Averages)
- [ ] Add "Generate Standard Gains" button that calls the calculation endpoint

#### Roster Management
- [ ] Add functionality to mark players as "on my team"
- [ ] Implement roster summary component showing current team stat projections

#### Optimization Interface
- [ ] Create budget input field
- [ ] Add "Generate Optimal Lineup" button 
- [ ] Design results display showing suggested optimal lineup

#### Player Analysis
- [ ] Create sortable table view of top 25 hitters by SGCalc
- [ ] Create sortable table view of top 25 pitchers by SGCalc
- [ ] Implement player detail modal showing stat impact visualization

### Data Visualization
- [ ] Implement radar chart or bar chart comparing current roster stats to threshold model
- [ ] Add visual indicators for categories where team is deficient
- [ ] Create "what-if" visualization showing impact of adding selected player

## Integration Tasks

- [ ] Set up state management for tracking current roster composition
- [ ] Implement caching of calculation results to improve performance
- [ ] Add loading indicators during API calls
- [ ] Create error handling for API failures
- [ ] Add ability to export/save optimal lineup results

## Optional Enhancements

- [ ] Implement "what-if" scenario saving functionality
- [ ] Add toggle between different optimization strategies (value maximization vs. category balance)
- [ ] Create auction tracking interface to update available players and budget in real-time
- [ ] Add player trend indicators based on recent performance or news
- [ ] Implement position eligibility tracking for multi-position players

## Testing
- [ ] Write unit tests for Standard Gains calculation
- [ ] Test optimization algorithm with various constraints
- [ ] Create end-to-end test for the complete workflow
- [ ] Perform performance testing with full player dataset
