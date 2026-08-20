import sqlite3
import json
import os
from datetime import datetime
import time


VOLUME_PATH = os.getenv(
    "RAILWAY_VOLUME_MOUNT_PATH",
    "."
)

DB_PATH = os.path.join(
    VOLUME_PATH,
    "school.db"
)


def init_db():
    conn = sqlite3.connect(DB_PATH)
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

    # Нові таблиці для управління чатом
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        platform TEXT DEFAULT 'telegram',
        user_message TEXT,
        bot_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS meta_message_reactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mid TEXT NOT NULL,
        platform TEXT NOT NULL,
        page_id TEXT NOT NULL,
        participant_id TEXT NOT NULL,
        reaction TEXT NOT NULL,
        reacted_by TEXT DEFAULT 'manager',
        created_at INTEGER NOT NULL,
        UNIQUE(mid, reacted_by)
    )
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_meta_conversations_page
    ON meta_conversations(page_id, last_message_at DESC)
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT UNIQUE NOT NULL,
        platform TEXT DEFAULT 'telegram',
        current_stage TEXT DEFAULT 'greeting',
        child_name TEXT,
        child_age INTEGER,
        interests TEXT,
        selected_course TEXT,
        preferred_date TEXT,
        preferred_time TEXT,
        parent_phone TEXT,
        application_status TEXT DEFAULT 'draft',
        wants_manager_contact INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        child_name TEXT NOT NULL,
        child_age INTEGER NOT NULL,
        selected_course TEXT NOT NULL,
        preferred_date TEXT,
        preferred_time TEXT,
        parent_phone TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, id DESC)")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS conversation_state (
        session_id TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'IDLE',
        child_name TEXT, child_age INTEGER, interests TEXT, selected_course TEXT,
        preferred_date TEXT, preferred_time TEXT, parent_phone TEXT,
        pending_callback INTEGER DEFAULT 0, confirmation_token TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trial_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_code TEXT UNIQUE,
        session_id TEXT NOT NULL, confirmation_token TEXT UNIQUE,
        child_name TEXT, child_age INTEGER, course TEXT,
        preferred_date TEXT, preferred_time TEXT, parent_phone TEXT,
        status TEXT DEFAULT 'new', source TEXT DEFAULT 'website_chat',
        manager_callback INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_meta_conversations_page ON meta_conversations(page_id, last_message_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_meta_messages_conversation ON meta_messages(page_id, participant_id, timestamp ASC)")

    conn.commit()
    conn.close()


# ===== Функції для керування чат-сесіями =====

def get_or_create_session(user_id, platform="telegram"):
    """Отримати або створити сесію користувача"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute(
        "SELECT * FROM chat_sessions WHERE user_id = ? AND platform = ?",
        (user_id, platform)
    )
    session = cur.fetchone()
    
    if not session:
        cur.execute("""
            INSERT INTO chat_sessions (user_id, platform, current_stage)
            VALUES (?, ?, ?)
        """, (user_id, platform, "greeting"))
        conn.commit()
    
    conn.close()
    return session


def get_session(user_id, platform="telegram"):
    """Отримати сесію користувача"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT user_id, platform, current_stage, child_name, child_age, 
               interests, selected_course, preferred_date, preferred_time, 
               parent_phone, application_status, wants_manager_contact
        FROM chat_sessions 
        WHERE user_id = ? AND platform = ?
    """, (user_id, platform))
    
    result = cur.fetchone()
    conn.close()
    
    if result:
        return {
            "user_id": result[0],
            "platform": result[1],
            "current_stage": result[2],
            "child_name": result[3],
            "child_age": result[4],
            "interests": result[5],
            "selected_course": result[6],
            "preferred_date": result[7],
            "preferred_time": result[8],
            "parent_phone": result[9],
            "application_status": result[10],
            "wants_manager_contact": result[11]
        }
    return None


def update_session(user_id, platform="telegram", **kwargs):
    """Оновити дані сесії користувача"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    updates = []
    values = []
    
    for key, value in kwargs.items():
        if key in ["current_stage", "child_name", "child_age", "interests", 
                   "selected_course", "preferred_date", "preferred_time", 
                   "parent_phone", "application_status", "wants_manager_contact"]:
            updates.append(f"{key} = ?")
            values.append(value)
    
    if updates:
        values.extend([user_id, platform])
        query = f"UPDATE chat_sessions SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND platform = ?"
        cur.execute(query, values)
        conn.commit()
    
    conn.close()


def save_chat_message_new(user_id, user_message, bot_response, platform="telegram"):
    """Зберегти повідомлення чату"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO chat_history (user_id, platform, user_message, bot_response)
        VALUES (?, ?, ?, ?)
    """, (user_id, platform, user_message, bot_response))
    
    conn.commit()
    conn.close()


def save_application(user_id, child_name, child_age, selected_course, preferred_date, preferred_time, parent_phone):
    """Зберегти заявку на навчання"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("""
        INSERT INTO applications 
        (user_id, child_name, child_age, selected_course, preferred_date, preferred_time, parent_phone)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, child_name, child_age, selected_course, preferred_date, preferred_time, parent_phone))
    
    conn.commit()
    app_id = cur.lastrowid
    conn.close()
    
    return app_id


def get_applications(status=None):
    """Отримати все заявки або за статусом"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    if status:
        cur.execute("SELECT * FROM applications WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cur.execute("SELECT * FROM applications ORDER BY created_at DESC")
    
    results = cur.fetchall()
    conn.close()
    
    return results


def save_lead(source, message):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO leads (source, message)
    VALUES (?, ?)
    """, (source, message))

    conn.commit()
    conn.close()


def save_chat_message(session_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()
    conn.close()


def get_chat_history(session_id, limit=12):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT role, content FROM chat_messages
        WHERE session_id = ?
        ORDER BY id DESC LIMIT ?
    """, (session_id, limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]


def get_conversation_state(session_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM conversation_state WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO conversation_state (session_id) VALUES (?)", (session_id,))
        conn.commit()
        cur.execute("SELECT * FROM conversation_state WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
    result = dict(row)
    conn.close()
    return result


def update_conversation_state(session_id, **values):
    allowed = {
        "state", "child_name", "child_age", "interests", "selected_course",
        "preferred_date", "preferred_time", "parent_phone",
        "pending_callback", "confirmation_token"
    }
    values = {key: value for key, value in values.items() if key in allowed}
    get_conversation_state(session_id)
    if not values:
        return get_conversation_state(session_id)
    assignments = ", ".join(f"{key} = ?" for key in values)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        f"UPDATE conversation_state SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        (*values.values(), session_id)
    )
    conn.commit()
    conn.close()
    return get_conversation_state(session_id)


def create_trial_lead(session_id, confirmation_token, state, source="website_chat", manager_callback=0):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT lead_code FROM trial_leads WHERE confirmation_token = ?", (confirmation_token,))
    existing = cur.fetchone()
    if existing:
        conn.close()
        return existing[0], False
    cur.execute("""
        INSERT INTO trial_leads (
            session_id, confirmation_token, child_name, child_age, course,
            preferred_date, preferred_time, parent_phone, source, manager_callback
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, confirmation_token, state.get("child_name"), state.get("child_age"),
        state.get("selected_course"), state.get("preferred_date"),
        state.get("preferred_time"), state.get("parent_phone"), source, manager_callback
    ))
    lead_id = cur.lastrowid
    lead_code = f"IT-{1000 + lead_id}"
    cur.execute("UPDATE trial_leads SET lead_code = ? WHERE id = ?", (lead_code, lead_id))
    conn.commit()
    conn.close()
    return lead_code, True


def save_google_tokens(email, access_token, refresh_token):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM google_tokens")

    cur.execute("""
    INSERT INTO google_tokens (email, access_token, refresh_token)
    VALUES (?, ?, ?)
    """, (email, access_token, refresh_token))

    conn.commit()
    conn.close()


def get_google_tokens():
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM google_tokens")

    conn.commit()
    conn.close()


def save_meta_tokens(facebook_user_id, name, email, access_token, token_type=None, expires_at=None):
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM meta_tokens")
    cur.execute("DELETE FROM meta_pages")

    conn.commit()
    conn.close()


def save_meta_pages(pages):
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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

def get_meta_conversation(
    page_id,
    participant_id,
    platform="facebook"
):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

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
      AND page_id = ?
      AND participant_id = ?
    LIMIT 1
    """, (
        platform,
        str(page_id),
        str(participant_id)
    ))

    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "platform": row[0],
        "page_id": row[1],
        "participant_id": row[2],
        "participant_name": row[3],
        "participant_avatar": row[4],
        "last_message": row[5],
        "last_message_at": row[6],
        "unread_count": row[7]
    }

def get_meta_messages(
    page_id,
    participant_id,
    platform="facebook",
    limit=200
):
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
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

def mark_meta_messages_delivered(
    page_id,
    participant_id,
    watermark=0,
    mids=None,
    platform="facebook"
):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    clean_mids = [
        str(mid)
        for mid in (mids or [])
        if mid
    ]

    if clean_mids:
        placeholders = ",".join(
            "?" for _ in clean_mids
        )

        cur.execute(f"""
        UPDATE meta_messages
        SET status = 'delivered'
        WHERE platform = ?
          AND page_id = ?
          AND participant_id = ?
          AND direction = 'out'
          AND mid IN ({placeholders})
          AND status != 'read'
        """, [
            platform,
            str(page_id),
            str(participant_id),
            *clean_mids
        ])

    if int(watermark or 0) > 0:
        cur.execute("""
        UPDATE meta_messages
        SET status = 'delivered'
        WHERE platform = ?
          AND page_id = ?
          AND participant_id = ?
          AND direction = 'out'
          AND timestamp <= ?
          AND status != 'read'
        """, (
            platform,
            str(page_id),
            str(participant_id),
            int(watermark)
        ))

    conn.commit()
    conn.close()


def mark_meta_messages_read(
    page_id,
    participant_id,
    watermark,
    platform="facebook"
):
    clean_watermark = int(
        watermark or 0
    )

    if clean_watermark <= 0:
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    UPDATE meta_messages
    SET status = 'read'
    WHERE platform = ?
      AND page_id = ?
      AND participant_id = ?
      AND direction = 'out'
      AND timestamp <= ?
    """, (
        platform,
        str(page_id),
        str(participant_id),
        clean_watermark
    ))

    conn.commit()
    conn.close()

def update_meta_conversation_profile(
    platform,
    page_id,
    participant_id,
    participant_name=None,
    participant_avatar=None
):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    UPDATE meta_conversations
    SET participant_name = COALESCE(NULLIF(?, ''), participant_name),
        participant_avatar = COALESCE(NULLIF(?, ''), participant_avatar),
        updated_at = CURRENT_TIMESTAMP
    WHERE platform = ?
      AND page_id = ?
      AND participant_id = ?
    """, (
        participant_name or "",
        participant_avatar or "",
        platform,
        str(page_id),
        str(participant_id)
    ))

    conn.commit()
    conn.close()

ALLOWED_META_REACTIONS = {
    "👍",
    "❤️",
    "😂",
    "😮",
    "😢",
    "😡"
}


def save_meta_message_reaction(
    mid,
    platform,
    page_id,
    participant_id,
    reaction,
    reacted_by="manager"
):
    reaction = str(reaction or "").strip()

    if reaction not in ALLOWED_META_REACTIONS:
        return {
            "success": False,
            "error": "Непідтримувана реакція."
        }

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO meta_message_reactions (
        mid,
        platform,
        page_id,
        participant_id,
        reaction,
        reacted_by,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(mid, reacted_by)
    DO UPDATE SET
        reaction = excluded.reaction,
        created_at = excluded.created_at
    """, (
        str(mid),
        str(platform),
        str(page_id),
        str(participant_id),
        reaction,
        str(reacted_by),
        int(time.time() * 1000)
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "mid": str(mid),
        "reaction": reaction
    }


def delete_meta_message_reaction(
    mid,
    reacted_by="manager"
):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
    DELETE FROM meta_message_reactions
    WHERE mid = ?
      AND reacted_by = ?
    """, (
        str(mid),
        str(reacted_by)
    ))

    conn.commit()
    conn.close()

    return {
        "success": True,
        "mid": str(mid)
    }


def get_meta_reactions_for_messages(message_ids):
    clean_ids = [
        str(mid)
        for mid in (message_ids or [])
        if mid
    ]

    if not clean_ids:
        return {}

    placeholders = ",".join(
        "?"
        for _ in clean_ids
    )

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(f"""
    SELECT
        mid,
        reaction,
        reacted_by,
        created_at
    FROM meta_message_reactions
    WHERE mid IN ({placeholders})
    """, clean_ids)

    rows = cur.fetchall()
    conn.close()

    result = {}

    for row in rows:
        mid = row[0]

        if mid not in result:
            result[mid] = []

        result[mid].append({
            "reaction": row[1],
            "reacted_by": row[2],
            "created_at": row[3]
        })

    return result
