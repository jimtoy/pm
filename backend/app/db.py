import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS board_columns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL REFERENCES boards(id),
    title TEXT NOT NULL,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_id INTEGER NOT NULL REFERENCES board_columns(id),
    title TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL REFERENCES boards(id),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

SEED_COLUMNS = [
    (
        "Backlog",
        [
            (
                "Align roadmap themes",
                "Draft quarterly themes with impact statements and metrics.",
            ),
            (
                "Gather customer signals",
                "Review support tags, sales notes, and churn feedback.",
            ),
        ],
    ),
    (
        "Discovery",
        [
            (
                "Prototype analytics view",
                "Sketch initial dashboard layout and key drill-downs.",
            ),
        ],
    ),
    (
        "In Progress",
        [
            (
                "Refine status language",
                "Standardize column labels and tone across the board.",
            ),
            (
                "Design card layout",
                "Add hierarchy and spacing for scanning dense lists.",
            ),
        ],
    ),
    (
        "Review",
        [
            (
                "QA micro-interactions",
                "Verify hover, focus, and loading states.",
            ),
        ],
    ),
    (
        "Done",
        [
            (
                "Ship marketing page",
                "Final copy approved and asset pack delivered.",
            ),
            (
                "Close onboarding sprint",
                "Document release notes and share internally.",
            ),
        ],
    ),
]


def get_db_path() -> Path:
    return Path(os.environ.get("DB_PATH", DEFAULT_DB_PATH))


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    _seed_if_empty(conn)


def _seed_if_empty(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
        return

    user_id = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        ("user", "not-checked-in-mvp"),
    ).lastrowid
    board_id = conn.execute(
        "INSERT INTO boards (user_id, name) VALUES (?, ?)",
        (user_id, "My Board"),
    ).lastrowid

    for column_position, (title, cards) in enumerate(SEED_COLUMNS):
        column_id = conn.execute(
            "INSERT INTO board_columns (board_id, title, position) VALUES (?, ?, ?)",
            (board_id, title, column_position),
        ).lastrowid
        for card_position, (card_title, details) in enumerate(cards):
            conn.execute(
                "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
                (column_id, card_title, details, card_position),
            )

    conn.commit()
