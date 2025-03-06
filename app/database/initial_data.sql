INSERT INTO Standings (ModelId, Description, R, HR, RBI, SB, AVG, W, K, ERA, WHIP, SVH)
VALUES 
    (1, '25th Percentile Playoff Thresholds', 967, 262, 951, 103, 0.254, 82, 1418, 3.75, 1.19, 94),
    (2, 'Playoff Averages', 972, 290, 934, 142, 0.262, 92, 1414, 3.59, 1.17, 106);

-- Insert Teams data
INSERT INTO Teams (TeamId, TeamName, Owner, Salary)
VALUES 
    (1, 'Blue Streak', 'Ryan Roethle', 290);

-- Insert empty TeamHitters record
INSERT INTO TeamHitters (HittingTeamId)
VALUES (1);

-- Insert empty TeamPitchers record
INSERT INTO TeamPitchers (PitchingTeamId)
VALUES (1);