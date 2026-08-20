"""
Утиліти для управління заявками та сесіями чату
Дозволяє переглядати, фільтрувати та експортувати дані
"""

import sqlite3
import json
from datetime import datetime
from db import DB_PATH, get_applications


def get_all_applications():
    """Отримати всі заявки"""
    return get_applications()


def get_pending_applications():
    """Отримати очікуючі заявки"""
    return get_applications("pending")


def print_applications(applications, limit=None):
    """Вивести заявки у таблиці"""
    if not applications:
        print("❌ Немає заявок")
        return
    
    print("\n" + "="*120)
    print(f"{'ID':<5} {'User ID':<30} {'Ім\'я':<15} {'Вік':<5} {'Курс':<20} {'Телефон':<15} {'Статус':<10} {'Дата':<20}")
    print("="*120)
    
    for app in applications[:limit]:
        user_id = app[1][:28] if len(app[1]) > 28 else app[1]
        print(f"{app[0]:<5} {user_id:<30} {app[2]:<15} {app[3]:<5} {app[4]:<20} {app[7]:<15} {app[8]:<10} {app[9]:<20}")
    
    print("="*120)
    print(f"\n📊 Всього: {len(applications)} заявок")\n\n\ndef export_applications_to_json(filename=\"applications.json\"):\n    \"\"\"Експортувати заявки в JSON\"\"\"\n    apps = get_all_applications()\n    data = []\n    \n    for app in apps:\n        data.append({\n            \"id\": app[0],\n            \"user_id\": app[1],\n            \"child_name\": app[2],\n            \"child_age\": app[3],\n            \"selected_course\": app[4],\n            \"preferred_date\": app[5],\n            \"preferred_time\": app[6],\n            \"parent_phone\": app[7],\n            \"status\": app[8],\n            \"created_at\": app[9],\n            \"updated_at\": app[10]\n        })\n    \n    with open(filename, \"w\", encoding=\"utf-8\") as f:\n        json.dump(data, f, ensure_ascii=False, indent=2)\n    \n    print(f\"✅ Експортовано {len(data)} заявок в {filename}\")\n\n\ndef export_applications_to_csv(filename=\"applications.csv\"):\n    \"\"\"Експортувати заявки в CSV\"\"\"\n    import csv\n    apps = get_all_applications()\n    \n    with open(filename, \"w\", newline=\"\", encoding=\"utf-8\") as f:\n        writer = csv.writer(f)\n        writer.writerow([\"ID\", \"User ID\", \"Ім'я\", \"Вік\", \"Курс\", \"Дата\", \"Час\", \"Телефон\", \"Статус\", \"Створено\", \"Оновлено\"])\n        \n        for app in apps:\n            writer.writerow(app)\n    \n    print(f\"✅ Експортовано {len(apps)} заявок в {filename}\")\n\n\ndef get_chat_history(user_id):\n    \"\"\"Отримати історію чату для користувача\"\"\"\n    conn = sqlite3.connect(DB_PATH)\n    cur = conn.cursor()\n    \n    cur.execute(\"\"\"\n        SELECT user_message, bot_response, created_at \n        FROM chat_history \n        WHERE user_id = ? \n        ORDER BY created_at ASC\n    \"\"\", (user_id,))\n    \n    results = cur.fetchall()\n    conn.close()\n    \n    return results\n\n\ndef print_chat_history(user_id):\n    \"\"\"Вивести історію чату\"\"\"\n    history = get_chat_history(user_id)\n    \n    if not history:\n        print(f\"❌ Немає історії чату для {user_id}\")\n        return\n    \n    print(f\"\\n📱 Історія чату для {user_id}:\\n\")\n    for i, (user_msg, bot_msg, created_at) in enumerate(history, 1):\n        print(f\"{i}. [{created_at}]\")\n        print(f\"   👤 Користувач: {user_msg}\")\n        print(f\"   🤖 Бот: {bot_msg}\")\n        print()\n\n\ndef get_stats():\n    \"\"\"Отримати статистику\"\"\"\n    conn = sqlite3.connect(DB_PATH)\n    cur = conn.cursor()\n    \n    # Всього заявок\n    cur.execute(\"SELECT COUNT(*) FROM applications\")\n    total_apps = cur.fetchone()[0]\n    \n    # Очікуючих\n    cur.execute(\"SELECT COUNT(*) FROM applications WHERE status = ?\", (\"pending\",))\n    pending_apps = cur.fetchone()[0]\n    \n    # Обробленних\n    cur.execute(\"SELECT COUNT(*) FROM applications WHERE status = ?\", (\"processed\",))\n    processed_apps = cur.fetchone()[0]\n    \n    # Активних сесій\n    cur.execute(\"SELECT COUNT(*) FROM chat_sessions WHERE current_stage != ?\", (\"completed\",))\n    active_sessions = cur.fetchone()[0]\n    \n    # Повідомлень\n    cur.execute(\"SELECT COUNT(*) FROM chat_history\")\n    total_messages = cur.fetchone()[0]\n    \n    # Популярні курси\n    cur.execute(\"\"\"\n        SELECT selected_course, COUNT(*) as count \n        FROM applications \n        GROUP BY selected_course \n        ORDER BY count DESC\n    \"\"\")\n    popular_courses = cur.fetchall()\n    \n    conn.close()\n    \n    print(\"\\n📊 СТАТИСТИКА ШКОЛИ\\n\")\n    print(f\"📋 Всього заявок: {total_apps}\")\n    print(f\"⏳ Очікуючих обробки: {pending_apps}\")\n    print(f\"✅ Обробленних: {processed_apps}\")\n    print(f\"👥 Активних сесій: {active_sessions}\")\n    print(f\"💬 Всього повідомлень: {total_messages}\")\n    \n    print(\"\\n🏆 Популярні курси:\")\n    for course, count in popular_courses:\n        print(f\"   {course}: {count} заявок\")\n\n\nif __name__ == \"__main__\":\n    import sys\n    \n    if len(sys.argv) < 2:\n        print(\"Утиліти управління заявками\")\n        print(\"\\nКоманди:\")\n        print(\"  admin.py all        - Показати всі заявки\")\n        print(\"  admin.py pending    - Показати очікуючі заявки\")\n        print(\"  admin.py stats      - Показати статистику\")\n        print(\"  admin.py export-json - Експортувати в JSON\")\n        print(\"  admin.py export-csv  - Експортувати в CSV\")\n        print(\"  admin.py history <user_id> - Показати історію чату\")\n        sys.exit()\n    \n    command = sys.argv[1]\n    \n    if command == \"all\":\n        apps = get_all_applications()\n        print_applications(apps)\n    elif command == \"pending\":\n        apps = get_pending_applications()\n        print_applications(apps)\n    elif command == \"stats\":\n        get_stats()\n    elif command == \"export-json\":\n        export_applications_to_json()\n    elif command == \"export-csv\":\n        export_applications_to_csv()\n    elif command == \"history\" and len(sys.argv) > 2:\n        user_id = sys.argv[2]\n        print_chat_history(user_id)\n    else:\n        print(f\"❌ Невідома команда: {command}\")\n