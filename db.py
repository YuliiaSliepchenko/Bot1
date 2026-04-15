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