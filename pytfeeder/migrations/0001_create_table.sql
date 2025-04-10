PRAGMA user_version=1;

CREATE TABLE tb_entries (
    id         TEXT     NOT NULL CHECK(length(id) == 11) PRIMARY KEY,
    title      TEXT     NOT NULL,
    published  DATETIME NOT NULL,
    channel_id TEXT     NOT NULL,
    is_viewed  TINYINT  NOT NULL DEFAULT 0
);
