PRAGMA user_version=2;

ALTER TABLE tb_entries
ADD COLUMN is_deleted TINYINT NOT NULL DEFAULT 0;
