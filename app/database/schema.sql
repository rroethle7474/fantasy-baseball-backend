-- Drop existing tables if they exist
DROP TABLE IF EXISTS Standings;
DROP TABLE IF EXISTS Teams;
DROP TABLE IF EXISTS TeamHitters;
DROP TABLE IF EXISTS TeamPitchers;
DROP TABLE IF EXISTS Hitters;
DROP TABLE IF EXISTS Pitchers;

-- Create Standings table
CREATE TABLE Standings (
    ModelId INTEGER PRIMARY KEY,
    Description TEXT NOT NULL,
    R INTEGER,
    HR INTEGER,
    RBI INTEGER,
    SB INTEGER,
    AVG REAL,
    W INTEGER,
    K INTEGER,
    ERA REAL,
    WHIP REAL,
    SVH INTEGER
);

-- Create Teams table
CREATE TABLE Teams (
    TeamId INTEGER PRIMARY KEY,
    TeamName TEXT NOT NULL,
    Owner TEXT,
    Salary REAL
);

-- Create TeamHitters table
CREATE TABLE TeamHitters (
    HittingTeamId INTEGER PRIMARY KEY,
    C INTEGER,
    FirstBase INTEGER,
    SecondBase INTEGER,
    ShortStop INTEGER,
    ThirdBase INTEGER,
    MiddleInfielder INTEGER,
    CornerInfielder INTEGER,
    Outfield1 INTEGER,
    Outfield2 INTEGER,
    Outfield3 INTEGER,
    Outfield4 INTEGER,
    Outfield5 INTEGER,
    Utility INTEGER,
    Bench1 INTEGER,
    Bench2 INTEGER,
    Bench3 INTEGER,
    FOREIGN KEY (HittingTeamId) REFERENCES Teams (TeamId) ON DELETE CASCADE,
    FOREIGN KEY (C) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (FirstBase) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (SecondBase) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (ShortStop) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (ThirdBase) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (MiddleInfielder) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (CornerInfielder) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Outfield1) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Outfield2) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Outfield3) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Outfield4) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Outfield5) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Utility) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Bench1) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Bench2) REFERENCES Hitters (HittingPlayerId),
    FOREIGN KEY (Bench3) REFERENCES Hitters (HittingPlayerId)
);

-- Create TeamPitchers table
CREATE TABLE TeamPitchers (
    PitchingTeamId INTEGER PRIMARY KEY,
    Pitcher1 INTEGER,
    Pitcher2 INTEGER,
    Pitcher3 INTEGER,
    Pitcher4 INTEGER,
    Pitcher5 INTEGER,
    Pitcher6 INTEGER,
    Pitcher7 INTEGER,
    Pitcher8 INTEGER,
    Pitcher9 INTEGER,
    Bench1 INTEGER,
    Bench2 INTEGER,
    Bench3 INTEGER,
    FOREIGN KEY (PitchingTeamId) REFERENCES Teams (TeamId) ON DELETE CASCADE,
    FOREIGN KEY (Pitcher1) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Pitcher2) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Pitcher3) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Pitcher4) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Pitcher5) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Pitcher6) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Pitcher7) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Pitcher8) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Pitcher9) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Bench1) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Bench2) REFERENCES Pitchers (PitchingPlayerId),
    FOREIGN KEY (Bench3) REFERENCES Pitchers (PitchingPlayerId)
);

-- Create Hitters table
CREATE TABLE Hitters (
    HittingPlayerId INTEGER PRIMARY KEY,
    PlayerName TEXT NOT NULL,
    Team TEXT,
    Position TEXT,
    Status TEXT,
    Age INTEGER,
    HittingTeamId INTEGER,
    OriginalSalary REAL,
    AdjustedSalary REAL,
    AuctionSalary REAL,
    G INTEGER,
    PA INTEGER,
    AB INTEGER,
    H INTEGER,
    HR INTEGER,
    R INTEGER,
    RBI INTEGER,
    BB INTEGER,
    HBP INTEGER,
    SB INTEGER,
    AVG REAL,
    FOREIGN KEY (HittingTeamId) REFERENCES TeamHitters (HittingTeamId)
);

-- Create Pitchers table
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
);