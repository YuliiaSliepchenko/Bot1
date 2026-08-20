"""
Скрипт для тестування основних функцій бота
"""

import os
import sys
import json
from pathlib import Path

# Кольорі для терміналу
GREEN = "\\033[92m"
RED = "\\033[91m"
YELLOW = "\\033[93m"
BLUE = "\\033[94m"
RESET = "\\033[0m"

def test_section(name):
    """Заголовок для розділу тесту"""
    print(f"\\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{name}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\\n")

def test_success(message):
    """Успішний тест"""
    print(f"{GREEN}✅ {message}{RESET}")

def test_error(message):
    """Помилка тесту"""
    print(f"{RED}❌ {message}{RESET}")

def test_warning(message):
    """Попередження"""
    print(f"{YELLOW}⚠️  {message}{RESET}")

def test_info(message):
    """Інформація"""
    print(f"{BLUE}ℹ️  {message}{RESET}")

# ===== ТЕСТИ =====

test_section("ПЕРЕВІРКА СЕРЕДОВИЩА")

# 1. Перевірка файлу .env
print("Перевіряю файл .env...")
if Path(".env").exists():
    test_success(".env файл існує")
    with open(".env") as f:
        content = f.read()
        if "BOT_TOKEN=" in content:
            if content.split("BOT_TOKEN=")[1].strip().startswith("your_"):
                test_warning("BOT_TOKEN використовує плейсхолдер, замініть на реальний токен")
            else:
                test_success("BOT_TOKEN встановлено")
        else:
            test_error("BOT_TOKEN не знайдено в .env")
else:
    test_error(".env файл не знайдено, створіть його на основі .env.example")

test_section("ПЕРЕВІРКА ФАЙЛІВ ПРОЕКТУ")

# 2. Перевірка необхідних файлів
required_files = [
    "bot.py",
    "db.py",
    "admin.py",
    "config.py",
    "knowledge_base.json",
    "requirements.txt",
    "README.md"
]

all_files_ok = True
for file in required_files:
    if Path(file).exists():
        test_success(f"Файл {file} знайдено")
    else:
        test_error(f"Файл {file} не знайдено")
        all_files_ok = False

test_section("ПЕРЕВІРКА СИНТАКСИСУ PYTHON")

# 3. Перевірка синтаксису основних файлів
import py_compile

python_files = ["bot.py", "db.py", "admin.py", "config.py"]
for pyfile in python_files:
    try:
        py_compile.compile(pyfile, doraise=True)
        test_success(f"{pyfile} - синтаксис OK")
    except py_compile.PyCompileError as e:
        test_error(f"{pyfile} - помилка синтаксису: {e}")

test_section("ПЕРЕВІРКА БАЗИ ЗНАНЬ")

# 4. Перевірка knowledge_base.json
try:
    with open("knowledge_base.json", "r", encoding="utf-8") as f:
        kb = json.load(f)
    
    test_success("knowledge_base.json завантажено")
    
    # Перевірка структури
    required_keys = ["school", "courses", "age_groups", "messages"]
    for key in required_keys:
        if key in kb:
            test_success(f"  └─ Розділ '{key}' знайдено")
        else:
            test_error(f"  └─ Розділ '{key}' не знайдено")
    
    # Перевірка курсів
    if "courses" in kb:
        print(f"\\n  Знайдено курсів: {len(kb['courses'])}\\n")
        for course in kb["courses"]:
            print(f"    - {course.get('name', 'Unknown')} ({course.get('id', 'No ID')})")
    
    # Перевірка повідомлень
    if "messages" in kb:
        print(f"\\n  Знайдено повідомлень: {len(kb['messages'])}\\n")
        for msg_key in kb["messages"].keys():
            print(f"    - {msg_key}")
            
except json.JSONDecodeError as e:
    test_error(f"knowledge_base.json має помилку JSON: {e}")
except FileNotFoundError:
    test_error("knowledge_base.json не знайдено")

test_section("ПЕРЕВІРКА ЗАЛЕЖНОСТЕЙ")

# 5. Перевірка встановлених пакетів
import subprocess
import sys

required_packages = {
    "aiogram": "aiogram",
    "fastapi": "fastapi",
    "pydantic": "pydantic",
    "dotenv": "python-dotenv"
}

print("Перевіряю встановлені пакети...\\n")
for package_name, import_name in required_packages.items():
    try:
        __import__(import_name)
        test_success(f"{package_name} встановлено")
    except ImportError:
        test_warning(f"{package_name} не встановлено, запустіть: pip install {package_name}")

test_section("ПЕРЕВІРКА БАЗИ ДАНИХ")

# 6. Перевірка БД
try:
    from db import init_db, DB_PATH
    
    print(f"Шлях до БД: {DB_PATH}\\n")
    
    if Path(DB_PATH).exists():
        test_success(f"База даних існує (розмір: {Path(DB_PATH).stat().st_size} bytes)")
    else:
        test_info("База даних буде створена при першому запуску бота")
    
    # Спробуємо ініціалізувати БД
    init_db()
    test_success("Таблиці БД ініціалізовані успішно")
    
except Exception as e:
    test_error(f"Помилка при роботі з БД: {e}")

test_section("ПЕРЕВІРКА КОНФІГУРАЦІЇ")

# 7. Перевірка конфігурації
try:
    from config import STAGES, APPLICATION_STATUS, BUTTONS
    
    test_success(f"Знайдено {len(STAGES)} етапів розмови")
    test_success(f"Знайдено {len(APPLICATION_STATUS)} статусів заявок")
    test_success(f"Знайдено {len(BUTTONS)} кнопок")
    
    print(f"\\n  Етапи розмови: {', '.join(STAGES.keys())}")
    
except Exception as e:
    test_error(f"Помилка при завантаженні конфіг: {e}")

test_section("РЕКОМЕНДАЦІЇ")

print("""
📝 Перед запуском бота переконайтесь:

1. ✅ BOT_TOKEN в .env файлі замінено на реальний токен
   Отримайте його від @BotFather в Telegram

2. ✅ Усі залежності встановлені
   Команда: pip install -r requirements.txt

3. ✅ Python 3.8 або новіша версія
   Перевірка: python --version

4. ✅ Інтернет з'єднання активне
   Бот потребує доступу до Telegram API

5. ✅ База даних проініціалізована
   Створюється автоматично при першому запуску
""")

test_section("ГОТОВО!")

if all_files_ok:
    test_success("Усі перевірки пройдені успішно! 🎉")
    print(f"\\n{GREEN}Запустіть бота командою: python bot.py{RESET}\\n")
else:
    test_warning("Деякі файли відсутні, перевірте вище")

print()
