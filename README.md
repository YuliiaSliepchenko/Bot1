# 🤖 ITENAISchool Telegram Bot

Автоматизований Telegram-бот для управління заявками на курси ITENAISchool.

## ✨ Можливості

✅ **Автоматичний сценарій розмови:**
- Визначення віку та інтересів дитини
- Рекомендація найкращих курсів
- Збір контактної інформації
- Підтвердження заявки

✅ **Управління базою даних:**
- Збереження історії чату
- Збереження заявок на курси
- Отримання статистики

✅ **Постійна кнопка контакту менеджера:**
- Номер менеджера: **+380 93 148 03 43**
- Доступна на всіх етапах розмови

## 🚀 Встановлення

### 1. Клонуйте репозиторій та встановіть залежності

```bash
cd Bot1
python -m venv venv
source venv/bin/activate  # На Windows: venv\\Scripts\\activate
pip install -r requirements.txt
```

### 2. Налаштуйте змінні середовища

Створіть файл `.env` в кореневій папці:

```env
BOT_TOKEN=вашTelegramBotToken
RAILWAY_VOLUME_MOUNT_PATH=./data
```

**Де отримати BOT_TOKEN:**
1. Напишіть [@BotFather](https://t.me/botfather) в Telegram
2. Команда: `/newbot`
3. Виберіть ім'я і юзернейм бота
4. Скопіюйте отриманий токен

### 3. Запустіть бота

```bash
python bot.py
```

## 📝 Сценарій розмови

```
1️⃣ Привіт → бот запитує вік дитини
2️⃣ Вік → бот запитує інтереси
3️⃣ Інтереси → бот пропонує курси
4️⃣ Вибір курсу → бот запитує ім'я
5️⃣ Ім'я → бот запитує телефон
6️⃣ Телефон → бот запитує час консультації
7️⃣ Час → бот показує підсумок
8️⃣ Підтвердження → заявка записується в БД
```

## 📊 Управління заявками

### Переглянути всі заявки

```bash
python admin.py all
```

### Переглянути очікуючі заявки

```bash
python admin.py pending
```

### Показати статистику

```bash
python admin.py stats
```

### Експортувати в JSON

```bash
python admin.py export-json
```

### Експортувати в CSV

```bash
python admin.py export-csv
```

### Переглянути історію чату користувача

```bash
python admin.py history telegram:123456789
```

## 📚 Курси

- 🐍 **Python** - Програмування з нуля (вік 8-18)
- 🎮 **Roblox Studio** - Розробка ігор (вік 7-16)
- 🤖 **AI & ChatGPT** - Штучний інтелект (вік 10-18)
- 🎨 **3D-моделювання** - Blender (вік 9-18)
- 📹 **Блогінг** - Створення контенту (вік 10-18)
- 💾 **Комп'ютерна грамотність** - Базові навички (вік 6-12)

## 📂 Структура проекту

```
Bot1/
├── bot.py                 # Основний Telegram бот
├── app.py                 # FastAPI сервер (чат API)
├── db.py                  # Управління базою даних
├── admin.py               # Утиліти для управління заявками
├── knowledge_base.json    # База знань про курси та повідомлення
├── requirements.txt       # Залежності Python
├── .env                   # Змінні середовища (не коміти!)
└── school.db              # SQLite база даних (автоматично створюється)
```

## 🗄️ Структура БД

### chat_sessions
Текущие сесії користувачів з інформацією про етап розмови

```sql
CREATE TABLE chat_sessions (
    id INTEGER PRIMARY KEY,
    user_id TEXT UNIQUE,
    current_stage TEXT,
    child_name TEXT,
    child_age INTEGER,
    interests TEXT,
    selected_course TEXT,
    preferred_date TEXT,
    preferred_time TEXT,
    parent_phone TEXT,
    application_status TEXT,
    wants_manager_contact INTEGER,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### applications
Завершені заявки на курси

```sql
CREATE TABLE applications (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    child_name TEXT,
    child_age INTEGER,
    selected_course TEXT,
    preferred_date TEXT,
    preferred_time TEXT,
    parent_phone TEXT,
    status TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### chat_history
Історія всіх повідомлень

```sql
CREATE TABLE chat_history (
    id INTEGER PRIMARY KEY,
    user_id TEXT,
    user_message TEXT,
    bot_response TEXT,
    created_at TIMESTAMP
);
```

## 🔧 Конфігурація

### knowledge_base.json

Редагуйте цей файл, щоб змінити:
- **Інформацію про школу** - опис, телефон менеджера
- **Список курсів** - назви, описи, рекомендований вік
- **Повідомлення бота** - усі текстові повідомлення
- **Вікові групи** - рекомендовані курси за віком

## 📞 Контакт з менеджером

Кнопка \"📞 Контакт менеджера\" доступна на всіх етапах розмови.

При натисненні показує:
```
📞 Контакт менеджера школи:
+380 93 148 03 43

Натисніть номер, щоб зателефонувати, або залиште свій номер — менеджер зв'яжеться з Вами.
```

## 🛠️ Командни для бота

- `/start` - Почати розмову
- `/reset` - Скинути сесію та почати заново

## ⚠️ Важливо

1. Бот зберігає всі дані локально в SQLite (school.db)
2. На продакшені використовуйте Cloud Database (PostgreSQL, MySQL)
3. Не комітьте `.env` файл з реальними токенами
4. Регулярно экспортуйте заявки для резервної копії

## 🔐 Безпека

- Ніколи не публікуйте BOT_TOKEN
- Захищайте доступ до admin.py
- Використовуйте HTTPS для API
- Валідуйте всі вхідні дані

## 📖 Документація

Детальна документація по API та структурі даних знаходиться в коментарях коду.

---

**Автор:** ITENAISchool Bot Team
**Версія:** 1.0.0
**Ліцензія:** Private
