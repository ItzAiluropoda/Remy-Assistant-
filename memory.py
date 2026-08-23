"""
memory.py
----------
Remy's memory system. This is the ONLY file that should ever touch the
database files directly - remy_comm.py just calls the functions below
and doesn't need to know there are three .db files behind them.

Three databases, per the design we settled on:

1. core.db
   Behaviors, standing preferences, available tools. Small, always loaded
   into every request. Lives in its own database (not hardcoded in this
   file) so it can be edited - by you, or later by Remy itself via
   "tool"/"preference" type interactions - without ever touching code.

2. interactions.db
   A timestamped log, categorized as: movement, call, contact, tool,
   preference. Write-only background history for now - not injected into
   prompts, just recorded so it exists for later review/summarization.

3. projects.db
   Full-detail project records, tagged. Only pulled into context when
   relevant (name mentioned, tag matches, or status is "active") - never
   preloaded in bulk, so token cost stays proportional to relevance.
"""

import os
import sqlite3
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# DATABASE PATHS
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_DB = os.path.join(BASE_DIR, "core.db")
INTERACTIONS_DB = os.path.join(BASE_DIR, "interactions.db")
PROJECTS_DB = os.path.join(BASE_DIR, "projects.db")


def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_databases():
    """
    Creates all three database files and their tables if they don't exist
    yet. Safe to call every time Remy starts - does nothing if already
    set up. Also seeds core.db with a minimal starter identity the very
    first time it's created, so Remy isn't blank on first run.
    """
    with _connect(CORE_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS core_identity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,     -- behavior | preference | tool
                content TEXT NOT NULL
            )
        """)
        # Seed only if the table is completely empty (first run ever).
        row_count = conn.execute("SELECT COUNT(*) FROM core_identity").fetchone()[0]
        if row_count == 0:
            conn.execute(
                "INSERT INTO core_identity (category, content) VALUES (?, ?)",
                ("behavior", "You are Remy, a personal desktop assistant. "
                             "Be concise, direct, and helpful."),
            )

    with _connect(INTERACTIONS_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT NOT NULL,     -- movement | call | contact | tool | preference
                device_type TEXT,           -- phone | pc | robot (only relevant for "contact")
                summary TEXT NOT NULL
            )
        """)

    with _connect(PROJECTS_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',   -- active | paused | done
                last_call TEXT,
                tags TEXT,                                -- comma-separated, e.g. "cooking,python"
                detail TEXT
            )
        """)


# ---------------------------------------------------------------------------
# 1. CORE IDENTITY - stored in core.db, manipulable without touching code
# ---------------------------------------------------------------------------

def get_core_identity():
    """
    Reads every row from core.db and formats it into a single text block
    for the system prompt. Always called, every turn - should stay small.
    """
    with _connect(CORE_DB) as conn:
        rows = conn.execute(
            "SELECT category, content FROM core_identity ORDER BY id"
        ).fetchall()

    behaviors = [r["content"] for r in rows if r["category"] == "behavior"]
    preferences = [r["content"] for r in rows if r["category"] == "preference"]
    tools = [r["content"] for r in rows if r["category"] == "tool"]

    lines = list(behaviors)

    if preferences:
        lines.append("Standing preferences:")
        lines.extend(f"- {p}" for p in preferences)

    if tools:
        lines.append("Available tools:")
        lines.extend(f"- {t}" for t in tools)

    return "\n".join(lines)


def add_core_entry(category, content):
    """
    Adds one entry to core.db. category should be "behavior", "preference",
    or "tool". This is how Remy's personality/tools/preferences grow over
    time - via this function, never by editing this file.
    """
    with _connect(CORE_DB) as conn:
        conn.execute(
            "INSERT INTO core_identity (category, content) VALUES (?, ?)",
            (category, content),
        )


def remove_core_entry(entry_id):
    """Removes one core_identity row by its id."""
    with _connect(CORE_DB) as conn:
        conn.execute("DELETE FROM core_identity WHERE id = ?", (entry_id,))


def list_core_entries():
    """Returns all core_identity rows (id, category, content) - useful for
    reviewing/editing what's currently stored."""
    with _connect(CORE_DB) as conn:
        return conn.execute(
            "SELECT id, category, content FROM core_identity ORDER BY category, id"
        ).fetchall()


# ---------------------------------------------------------------------------
# 2. INTERACTIONS - logging
# ---------------------------------------------------------------------------

def log_interaction(category, summary, device_type=None):
    """
    Records one interaction. category should be one of:
    "movement", "call", "contact", "tool", "preference".
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect(INTERACTIONS_DB) as conn:
        conn.execute(
            "INSERT INTO interactions (timestamp, category, device_type, summary) "
            "VALUES (?, ?, ?, ?)",
            (timestamp, category, device_type, summary),
        )


# ---------------------------------------------------------------------------
# 3. PROJECTS - retrieval and management
# ---------------------------------------------------------------------------

def add_project(title, tags=None, detail="", status="active"):
    """Creates a new project record. tags is a list of strings."""
    tags_str = ",".join(tags) if tags else ""
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect(PROJECTS_DB) as conn:
        conn.execute(
            "INSERT INTO projects (title, status, last_call, tags, detail) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, status, timestamp, tags_str, detail),
        )


def update_project_status(title, new_status):
    """Updates a project's status (active | paused | done) by title."""
    with _connect(PROJECTS_DB) as conn:
        conn.execute(
            "UPDATE projects SET status = ? WHERE title = ?",
            (new_status, title),
        )


def get_relevant_projects(user_text):
    """
    Returns a text block of any projects worth injecting into this turn's
    system prompt, based on:
      a) the project's title is mentioned in user_text
      b) one of the project's tags appears in user_text
      c) the project's status is "active"
    Returns "" if nothing matches - most turns should return nothing.
    """
    user_text_lower = user_text.lower()
    matched = []

    with _connect(PROJECTS_DB) as conn:
        rows = conn.execute("SELECT * FROM projects").fetchall()

    for row in rows:
        title = row["title"]
        tags = [t.strip() for t in (row["tags"] or "").split(",") if t.strip()]
        status = row["status"]

        name_match = title.lower() in user_text_lower
        tag_match = any(tag.lower() in user_text_lower for tag in tags)
        is_active = status == "active"

        if name_match or tag_match or is_active:
            matched.append(row)

    if not matched:
        return ""

    # Update last_call only for genuine relevance hits (not just for being
    # active, since active projects surface every turn regardless).
    timestamp = datetime.now(timezone.utc).isoformat()
    with _connect(PROJECTS_DB) as conn:
        for row in matched:
            conn.execute(
                "UPDATE projects SET last_call = ? WHERE id = ?",
                (timestamp, row["id"]),
            )

    blocks = []
    for row in matched:
        blocks.append(f"[{row['title']}] (status: {row['status']})\n{row['detail']}")

    return "\n\n".join(blocks)


# Run once on import so all three databases always exist before anything
# queries them.
init_databases()
