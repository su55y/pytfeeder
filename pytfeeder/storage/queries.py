QUERIES = [
    "PRAGMA foreign_keys = ON;",
    """
    CREATE TABLE IF NOT EXISTS tb_entries(
        id TEXT NOT NULL CHECK(length(id) == 11) PRIMARY KEY,
        title TEXT NOT NULL,
        updated DATETIME NOT NULL,
        channel_id TEXT NOT NULL,
        is_viewed TINYINT NOT NULL DEFAULT 0
    );""",
]
