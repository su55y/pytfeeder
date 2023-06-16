QUERIES = [
    "PRAGMA foreign_keys = ON;",
    """
    CREATE TABLE IF NOT EXISTS tb_feeds(
        channel_id TEXT NOT NULL CHECK(length(channel_id) == 24) PRIMARY KEY,
        title TEXT NOT NULL,
        is_active TINYINT NOT NULL DEFAULT 1
    );""",
    """
    CREATE TABLE IF NOT EXISTS tb_entries(
        id TEXT NOT NULL CHECK(length(id) == 11) PRIMARY KEY,
        title TEXT NOT NULL,
        updated DATETIME NOT NULL,
        channel_id TEXT NOT NULL REFERENCES tb_feeds(channel_id) ON DELETE CASCADE,
        is_viewed TINYINT NOT NULL DEFAULT 0
    );""",
]
