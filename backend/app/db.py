import os
import sqlite3

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./app.db").replace("sqlite:///", "")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 参照整合のために外部キーを有効に
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            title TEXT,
            thumbnail_url TEXT,
            rating INTEGER,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS video_tags (
            video_id TEXT,
            tag TEXT,
            PRIMARY KEY (video_id, tag),
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );
        """)
