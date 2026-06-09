import sqlite3
import json


def init_db():
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT,
        message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS google_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        access_token TEXT,
        refresh_token TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS meta_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        facebook_user_id TEXT,
        name TEXT,
        email TEXT,
        access_token TEXT,
        token_type TEXT,
        expires_at INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS meta_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        page_id TEXT UNIQUE,
        name TEXT,
        category TEXT,
        access_token TEXT,
        tasks TEXT,
        selected INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()


def save_lead(source, message):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO leads (source, message)
    VALUES (?, ?)
    """, (source, message))

    conn.commit()
    conn.close()


def save_google_tokens(email, access_token, refresh_token):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM google_tokens")

    cur.execute("""
    INSERT INTO google_tokens (email, access_token, refresh_token)
    VALUES (?, ?, ?)
    """, (email, access_token, refresh_token))

    conn.commit()
    conn.close()


def get_google_tokens():
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT email, access_token, refresh_token
    FROM google_tokens
    ORDER BY id DESC
    LIMIT 1
    """)

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "email": row[0],
        "access_token": row[1],
        "refresh_token": row[2]
    }


def delete_google_tokens():
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM google_tokens")

    conn.commit()
    conn.close()


def save_meta_tokens(facebook_user_id, name, email, access_token, token_type=None, expires_at=None):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM meta_tokens")

    cur.execute("""
    INSERT INTO meta_tokens (
        facebook_user_id,
        name,
        email,
        access_token,
        token_type,
        expires_at
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        facebook_user_id,
        name,
        email,
        access_token,
        token_type,
        expires_at
    ))

    conn.commit()
    conn.close()


def get_meta_tokens():
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT facebook_user_id, name, email, access_token, token_type, expires_at
    FROM meta_tokens
    ORDER BY id DESC
    LIMIT 1
    """)

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "facebook_user_id": row[0],
        "name": row[1],
        "email": row[2],
        "access_token": row[3],
        "token_type": row[4],
        "expires_at": row[5]
    }


def delete_meta_tokens():
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM meta_tokens")
    cur.execute("DELETE FROM meta_pages")

    conn.commit()
    conn.close()


def save_meta_pages(pages):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM meta_pages")

    for page in pages:
        cur.execute("""
        INSERT OR REPLACE INTO meta_pages (
            page_id,
            name,
            category,
            access_token,
            tasks,
            selected
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            page.get("id"),
            page.get("name"),
            page.get("category"),
            page.get("access_token"),
            json.dumps(page.get("tasks", []), ensure_ascii=False),
            0
        ))

    conn.commit()
    conn.close()


def get_meta_pages():
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT page_id, name, category, access_token, tasks, selected
    FROM meta_pages
    ORDER BY name ASC
    """)

    rows = cur.fetchall()
    conn.close()

    pages = []

    for row in rows:
        try:
            tasks = json.loads(row[4] or "[]")
        except Exception:
            tasks = []

        pages.append({
            "page_id": row[0],
            "name": row[1],
            "category": row[2],
            "access_token": row[3],
            "tasks": tasks,
            "selected": bool(row[5])
        })

    return pages