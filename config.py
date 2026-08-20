"""
Конфігурація розмови та етапи
"""

# Етапи розмови (conversation stages)
STAGES = {
    "greeting": "greeting",           # Привіт
    "age_ask": "age_ask",             # Запит віку
    "interests_ask": "interests_ask",   # Запит інтересів
    "course_select": "course_select",   # Вибір курсу
    "name_ask": "name_ask",           # Запит імені дитини
    "phone_ask": "phone_ask",         # Запит телефону
    "time_ask": "time_ask",           # Запит часу
    "confirmation": "confirmation",   # Підтвердження
    "completed": "completed"          # Завершено
}

# Статуси заявок
APPLICATION_STATUS = {
    "draft": "draft",               # Чернетка
    "pending": "pending",           # Очікує обробки
    "submitted": "submitted",       # Надіслана
    "processed": "processed",       # Обробленна
    "rejected": "rejected"          # Відхилена
}

# Валідація вісти
AGE_MIN = 5
AGE_MAX = 99
PHONE_MIN_LENGTH = 10
NAME_MIN_LENGTH = 2

# Налаштування бази даних
DB_CONFIG = {
    "type": "sqlite",
    "path": "school.db",
    "timeout": 5.0
}

# Повідомлення про помилки
ERROR_MESSAGES = {
    "invalid_age": "❌ Введіть цифру від {min} до {max}.",
    "invalid_phone": "❌ Введіть коректний номер телефону (мінімум {min} цифр).",
    "invalid_name": "❌ Будь ласка, введіть повне ім'я дитини.",
    "invalid_course": "❌ Будь ласка, оберіть один з запропонованих курсів.",
    "no_courses": "❌ На жаль, немає курсів для цього віку.",
    "general": "❌ Виникла помилка. Спробуйте ще раз або напишіть менеджеру."
}

# Кнопки
BUTTONS = {
    "manager_contact": "📞 Контакт менеджера",
    "confirm_yes": "✅ Так, записати",
    "confirm_no": "❌ Змінити дані"
}

# Логування
LOG_CONFIG = {
    "level": "INFO",
    "format": "[%(asctime)s] %(levelname)s: %(message)s",
    "file": "bot.log"
}
