-- Service-owned staffing tables (same Azure SQL database as PT / ZingHR / rv2_*)
-- Run once with DBA approval. Do not alter source tables.

IF OBJECT_ID(N'dbo.rv_staffing_Demand', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_Demand (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    ProjectId       NVARCHAR(128) NOT NULL,
    ProposalNumber  NVARCHAR(64) NULL,
    SubProjectName  NVARCHAR(256) NULL,
    PositionId      NVARCHAR(128) NULL,
    StartDate       DATE NOT NULL,
    EndDate         DATE NOT NULL,
    FiltersJson     NVARCHAR(MAX) NOT NULL DEFAULT N'{}',
    RequiredSkills  NVARCHAR(MAX) NOT NULL DEFAULT N'[]',
    Status          NVARCHAR(32) NOT NULL DEFAULT N'open',
    CreatedAtUtc    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CreatedBy       NVARCHAR(128) NOT NULL
);

IF OBJECT_ID(N'dbo.rv_staffing_Candidate', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_Candidate (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    DemandId        CHAR(36) NOT NULL,
    EmployeeKey     NVARCHAR(64) NOT NULL,
    Status          NVARCHAR(64) NOT NULL,
    CreatedAtUtc    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID(N'dbo.rv_staffing_CandidateMonth', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_CandidateMonth (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    CandidateId     CHAR(36) NOT NULL,
    MonthKey        DATE NOT NULL,
    Hours           DECIMAL(18,4) NOT NULL
);

IF OBJECT_ID(N'dbo.rv_staffing_Reservation', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_Reservation (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    CandidateId     CHAR(36) NOT NULL,
    DemandId        CHAR(36) NOT NULL,
    EmployeeKey     NVARCHAR(64) NOT NULL,
    MonthKey        DATE NOT NULL,
    Hours           DECIMAL(18,4) NOT NULL,
    Status          NVARCHAR(32) NOT NULL,
    IdempotencyKey  NVARCHAR(128) NOT NULL,
    CreatedAtUtc    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_rv_staffing_res UNIQUE (EmployeeKey, MonthKey, DemandId),
    CONSTRAINT UQ_rv_staffing_idem UNIQUE (IdempotencyKey)
);

IF OBJECT_ID(N'dbo.rv_staffing_Interview', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_Interview (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    CandidateId     CHAR(36) NOT NULL,
    Status          NVARCHAR(32) NOT NULL,
    BookedAtUtc     DATETIME2 NOT NULL,
    ExpiresAtUtc    DATETIME2 NOT NULL,
    Outcome         NVARCHAR(32) NULL,
    RejectionType   NVARCHAR(32) NULL,
    RejectionReason NVARCHAR(MAX) NULL
);

IF COL_LENGTH(N'dbo.rv_staffing_Interview', N'RejectionType') IS NULL
    ALTER TABLE dbo.rv_staffing_Interview ADD RejectionType NVARCHAR(32) NULL;

IF OBJECT_ID(N'dbo.rv_staffing_KbRequest', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_KbRequest (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    CandidateId     CHAR(36) NOT NULL,
    Status          NVARCHAR(32) NOT NULL,
    TrainingDays    INT NOT NULL DEFAULT 0,
    BufferDays      INT NOT NULL DEFAULT 0,
    PayloadJson     NVARCHAR(MAX) NOT NULL DEFAULT N'{}',
    Reason          NVARCHAR(MAX) NULL,
    CreatedAtUtc    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    UpdatedAtUtc    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID(N'dbo.rv_staffing_HiringRequest', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_HiringRequest (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    ProjectId       NVARCHAR(128) NOT NULL,
    Capability      NVARCHAR(256) NOT NULL,
    Headcount       INT NOT NULL,
    Justification   NVARCHAR(MAX) NOT NULL,
    Status          NVARCHAR(64) NOT NULL,
    PayloadJson     NVARCHAR(MAX) NOT NULL DEFAULT N'{}',
    CreatedAtUtc    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID(N'dbo.rv_staffing_Outbox', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_Outbox (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    EventType       NVARCHAR(64) NOT NULL,
    PayloadJson     NVARCHAR(MAX) NOT NULL,
    Published       BIT NOT NULL DEFAULT 0,
    CreatedAtUtc    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID(N'dbo.rv_staffing_AuditLog', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_AuditLog (
    Id              CHAR(36) NOT NULL PRIMARY KEY,
    Actor           NVARCHAR(128) NOT NULL,
    Action          NVARCHAR(64) NOT NULL,
    EntityType      NVARCHAR(64) NOT NULL,
    EntityId        CHAR(36) NOT NULL,
    DetailsJson     NVARCHAR(MAX) NOT NULL,
    CreatedAtUtc    DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

IF OBJECT_ID(N'dbo.rv_staffing_EmployeeBlock', N'U') IS NULL
CREATE TABLE dbo.rv_staffing_EmployeeBlock (
    Id                  CHAR(36) NOT NULL PRIMARY KEY,
    EmployeeKey         NVARCHAR(64) NOT NULL,
    CandidateId         CHAR(36) NOT NULL,
    DemandId            CHAR(36) NOT NULL,
    ProjectId           NVARCHAR(128) NOT NULL,
    ActorId             NVARCHAR(128) NOT NULL,
    ActorDisplayName    NVARCHAR(256) NOT NULL,
    Status              NVARCHAR(32) NOT NULL DEFAULT N'Active',
    ReleaseReason       NVARCHAR(256) NULL,
    CreatedAtUtc        DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    ReleasedAtUtc       DATETIME2 NULL,
    CONSTRAINT UQ_rv_staffing_block_candidate UNIQUE (CandidateId)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_EmployeeBlock_Employee')
    CREATE INDEX IX_rv_staffing_EmployeeBlock_Employee ON dbo.rv_staffing_EmployeeBlock (EmployeeKey, Status);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_Candidate_Demand')
    CREATE INDEX IX_rv_staffing_Candidate_Demand ON dbo.rv_staffing_Candidate (DemandId);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_Reservation_Cand')
    CREATE INDEX IX_rv_staffing_Reservation_Cand ON dbo.rv_staffing_Reservation (CandidateId, Status);

-- Indexes for the hot read paths (pool search, workflow polling, final check).
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_Demand_Project')
    CREATE INDEX IX_rv_staffing_Demand_Project ON dbo.rv_staffing_Demand (ProjectId) INCLUDE (Status, PositionId);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_CandidateMonth_Cand')
    CREATE INDEX IX_rv_staffing_CandidateMonth_Cand ON dbo.rv_staffing_CandidateMonth (CandidateId) INCLUDE (MonthKey, Hours);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_Reservation_Active')
    CREATE INDEX IX_rv_staffing_Reservation_Active ON dbo.rv_staffing_Reservation (Status)
        INCLUDE (EmployeeKey, MonthKey, Hours, DemandId);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_Interview_Due')
    CREATE INDEX IX_rv_staffing_Interview_Due ON dbo.rv_staffing_Interview (Status, ExpiresAtUtc) INCLUDE (CandidateId, BookedAtUtc);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_Interview_Cand')
    CREATE INDEX IX_rv_staffing_Interview_Cand ON dbo.rv_staffing_Interview (CandidateId, Status) INCLUDE (BookedAtUtc);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_KbRequest_Cand')
    CREATE INDEX IX_rv_staffing_KbRequest_Cand ON dbo.rv_staffing_KbRequest (CandidateId, Status);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_EmployeeBlock_Active')
    CREATE INDEX IX_rv_staffing_EmployeeBlock_Active ON dbo.rv_staffing_EmployeeBlock (Status)
        INCLUDE (EmployeeKey, CandidateId, ProjectId, DemandId, ActorId, ActorDisplayName);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_EmployeeBlock_Cand')
    CREATE INDEX IX_rv_staffing_EmployeeBlock_Cand ON dbo.rv_staffing_EmployeeBlock (CandidateId, Status);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_AuditLog_Created')
    CREATE INDEX IX_rv_staffing_AuditLog_Created ON dbo.rv_staffing_AuditLog (CreatedAtUtc DESC);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_rv_staffing_Outbox_Pending')
    CREATE INDEX IX_rv_staffing_Outbox_Pending ON dbo.rv_staffing_Outbox (Published, CreatedAtUtc);
