# ⚡ Швидкий старт

Цей посібник допоможе вам запустити бота за 5 хвилин.

## 📋 Вимоги

- Python 3.8+
- pip
- Telegram аккаунт
- Текстовий редактор

## 🎯 Крок 1: Отримайте BOT_TOKEN

1. Відкрийте Telegram і знайдіть [@BotFather](https://t.me/botfather)
2. Напишіть `/newbot`
3. Виберіть ім'я для бота (наприклад: `ITENAISchool_Bot`)
4. Виберіть юзернейм (наприклад: `itenaischool_bot`)
5. BotFather надасть вам токен, скопіюйте його

## 🚀 Крок 2: Налаштування

### 2.1 Клонуйте проект

```bash
cd Bot1
```

### 2.2 Створіть середовище Python

```bash
# На Windows
python -m venv venv
venv\Scripts\activate

# На MacOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2.3 Встановіть залежності

```bash
pip install -r requirements.txt
```

### 2.4 Налаштуйте `.env` файл

Створіть файл `.env` в папці проекту:

```
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTuvWxyZ
```

Замініть токен на ваш реальний токен від BotFather.

## 🤖 Крок 3: Запуск бота

```bash
python bot.py
```

Мають побачити:
```
✅ Bot started @your_bot_username
```

## 💬 Крок 4: Тестування

1. Відкрийте Telegram
2. Знайдіть вашого бота по юзернейму
3. Натисніть `/start`
4. Пройдіть усю розмову до кінця

## 📊 Крок 5: Перегляд заявок

Відкрийте новий термінал (вихідний залиште запущеним):

```bash
python admin.py all
```

Побачите список усіх заявок!

## 🔧 Додаткові команди

### Переглянути статистику
```bash
python admin.py stats
```

### Експортувати заявки в JSON
```bash
python admin.py export-json
```

Будуть створений файл `applications.json`

### Експортувати заявки в CSV
```bash
python admin.py export-csv
```

Будуть створений файл `applications.csv` для Excel/Google Sheets

## ✅ Готово!

Ваш бот готовий до роботи! 🎉

## 🆘 Проблеми?

### Проблема: \"BOT_TOKEN not found\"
- ✅ Перевірте, чи вы создали файл `.env`
- ✅ Перевірте, чи скопіювали токен правильно
- ✅ Перевірте, немає пробілів в токені

### Проблема: \"Module not found\"
- ✅ Переконайтесь, що середовище активовано: `venv\Scripts\activate`
- ✅ Встановіть залежності: `pip install -r requirements.txt`

### Проблема: Бот не відповідає
- ✅ Перевірте, чи запущений скрипт в терміналі
- ✅ Перевірте інтернет з'єднання
- ✅ Спробуйте перезавантажити бота: `Ctrl+C` і потім `python bot.py`

## 📚 Наступні кроки

- 📖 Читайте [README.md](README.md) для детальної документації
- ⚙️ Редагуйте [knowledge_base.json](knowledge_base.json) для зміни інформації про курси
- 🛠️ Завдання API: див. [app.py](app.py)

---

**Маєте запитання?** Напишіть менеджеру: +380 93 148 03 43
