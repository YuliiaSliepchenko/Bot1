import sqlite3

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