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

        cur.execute("""
    CREATE TABLE IF NOT EXISTS meta_conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL DEFAULT 'facebook',
        page_id TEXT NOT NULL,
        participant_id TEXT NOT NULL,
        participant_name TEXT,
        participant_avatar TEXT,
        last_message TEXT,
        last_message_at INTEGER,
        unread_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(platform, page_id, participant_id)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS meta_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mid TEXT UNIQUE,
        platform TEXT NOT NULL DEFAULT 'facebook',
        page_id TEXT NOT NULL,
        participant_id TEXT NOT NULL,
        direction TEXT NOT NULL,
        text TEXT,
        message_type TEXT DEFAULT 'text',
        attachment_url TEXT,
        timestamp INTEGER,
        status TEXT DEFAULT 'received',
        raw_payload TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_meta_conversations_page
    ON meta_conversations(page_id, last_message_at DESC)
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_meta_messages_conversation
    ON meta_messages(page_id, participant_id, timestamp ASC)
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

def get_meta_page(page_id):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT page_id, name, category, access_token, tasks, selected
    FROM meta_pages
    WHERE page_id = ?
    LIMIT 1
    """, (str(page_id),))

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    try:
        tasks = json.loads(row[4] or "[]")
    except Exception:
        tasks = []

    return {
        "page_id": row[0],
        "name": row[1],
        "category": row[2],
        "access_token": row[3],
        "tasks": tasks,
        "selected": bool(row[5])
    }

def save_meta_message(
    mid,
    platform,
    page_id,
    participant_id,
    direction,
    text,
    timestamp,
    message_type="text",
    attachment_url=None,
    status="received",
    raw_payload=None,
    participant_name=None,
    participant_avatar=None
):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    raw_json = json.dumps(
        raw_payload or {},
        ensure_ascii=False
    )

    cur.execute("""
    INSERT OR IGNORE INTO meta_messages (
        mid,
        platform,
        page_id,
        participant_id,
        direction,
        text,
        message_type,
        attachment_url,
        timestamp,
        status,
        raw_payload
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(mid) if mid else None,
        platform,
        str(page_id),
        str(participant_id),
        direction,
        text,
        message_type,
        attachment_url,
        int(timestamp or 0),
        status,
        raw_json
    ))

    inserted = cur.rowcount > 0

    if not inserted:
        conn.commit()
        conn.close()
        return False

    cur.execute("""
    SELECT id, participant_name, participant_avatar
    FROM meta_conversations
    WHERE platform = ?
      AND page_id = ?
      AND participant_id = ?
    LIMIT 1
    """, (
        platform,
        str(page_id),
        str(participant_id)
    ))

    conversation = cur.fetchone()
    unread_add = 1 if direction == "in" else 0

    if conversation:
        old_name = conversation[1] or ""
        old_avatar = conversation[2] or ""

        cur.execute("""
        UPDATE meta_conversations
        SET participant_name = ?,
            participant_avatar = ?,
            last_message = ?,
            last_message_at = ?,
            unread_count = unread_count + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """, (
            participant_name or old_name,
            participant_avatar or old_avatar,
            text,
            int(timestamp or 0),
            unread_add,
            conversation[0]
        ))

    else:
        cur.execute("""
        INSERT INTO meta_conversations (
            platform,
            page_id,
            participant_id,
            participant_name,
            participant_avatar,
            last_message,
            last_message_at,
            unread_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            platform,
            str(page_id),
            str(participant_id),
            participant_name,
            participant_avatar,
            text,
            int(timestamp or 0),
            unread_add
        ))

    conn.commit()
    conn.close()

    return True

def get_meta_conversations(page_id=None, platform="facebook", limit=100):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    if page_id:
        cur.execute("""
        SELECT
            platform,
            page_id,
            participant_id,
            participant_name,
            participant_avatar,
            last_message,
            last_message_at,
            unread_count
        FROM meta_conversations
        WHERE page_id = ?
          AND platform = ?
        ORDER BY last_message_at DESC
        LIMIT ?
        """, (
            str(page_id),
            platform,
            max(1, min(int(limit), 300))
        ))
    else:
        cur.execute("""
        SELECT
            platform,
            page_id,
            participant_id,
            participant_name,
            participant_avatar,
            last_message,
            last_message_at,
            unread_count
        FROM meta_conversations
        WHERE platform = ?
        ORDER BY last_message_at DESC
        LIMIT ?
        """, (
            platform,
            max(1, min(int(limit), 300))
        ))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "platform": row[0],
            "page_id": row[1],
            "participant_id": row[2],
            "participant_name": row[3],
            "participant_avatar": row[4],
            "last_message": row[5],
            "last_message_at": row[6],
            "unread_count": row[7]
        }
        for row in rows
    ]

def get_meta_messages(
    page_id,
    participant_id,
    platform="facebook",
    limit=200
):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT
        mid,
        platform,
        page_id,
        participant_id,
        direction,
        text,
        message_type,
        attachment_url,
        timestamp,
        status
    FROM meta_messages
    WHERE platform = ?
      AND page_id = ?
      AND participant_id = ?
    ORDER BY timestamp ASC, id ASC
    LIMIT ?
    """, (
        platform,
        str(page_id),
        str(participant_id),
        max(1, min(int(limit), 500))
    ))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "mid": row[0],
            "platform": row[1],
            "page_id": row[2],
            "participant_id": row[3],
            "direction": row[4],
            "text": row[5],
            "message_type": row[6],
            "attachment_url": row[7],
            "timestamp": row[8],
            "status": row[9]
        }
        for row in rows
    ]

def mark_meta_conversation_read(
    page_id,
    participant_id,
    platform="facebook"
):
    conn = sqlite3.connect("school.db")
    cur = conn.cursor()

    cur.execute("""
    UPDATE meta_conversations
    SET unread_count = 0,
        updated_at = CURRENT_TIMESTAMP
    WHERE platform = ?
      AND page_id = ?
      AND participant_id = ?
    """, (
        platform,
        str(page_id),
        str(participant_id)
    ))

    conn.commit()
    conn.close()