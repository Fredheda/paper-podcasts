-- papers: one row per processed paper, replacing local paper_state.json when
-- STORAGE_BACKEND=azure. Run via the Azure Portal Query Editor (or sqlcmd)
-- against PlaygroundDB; idempotent (IF NOT EXISTS).
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'papers')
BEGIN
    CREATE TABLE papers (
        arxiv_id NVARCHAR(32) NOT NULL PRIMARY KEY,
        cleaned_title NVARCHAR(200) NOT NULL,
        title NVARCHAR(500) NOT NULL,
        authors NVARCHAR(MAX) NOT NULL,        -- JSON array of {name, affiliation}
        abstract NVARCHAR(MAX) NOT NULL,
        published DATETIME2 NOT NULL,
        status NVARCHAR(50) NOT NULL,          -- state-machine state, e.g. "completed"
        listen_status NVARCHAR(20) NOT NULL DEFAULT 'unlistened',
        last_listened_at DATETIME2 NULL,
        created_at DATETIME2 NOT NULL,
        updated_at DATETIME2 NOT NULL
    );
END
