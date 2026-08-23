import json
import re
from pathlib import Path
from uuid import uuid4

from db import create_trial_lead, get_conversation_state, update_conversation_state


KNOWLEDGE = json.loads((Path(__file__).with_name("courses.json")).read_text(encoding="utf-8"))
COURSES = KNOWLEDGE["courses"]
PHONE = KNOWLEDGE["school"]["manager_phone_display"]

INTEREST_BUTTONS = [
    ("photoshop", "🎨 Photoshop / малювання"),
    ("after_effects", "🎬 After Effects / анімація"),
    ("ai", "🤖 Штучний інтелект"),
    ("digital_design", "✨ Цифровий дизайн"),
    ("unsure", "🤷 Ще не визначились")
]

AGE_BUTTONS = [(f"age:{age}", str(age)) for age in range(6, 19)]
COURSE_BUTTONS = [(course_id, course["name"]) for course_id, course in COURSES.items()]
DAY_BUTTONS = [
    ("date:П’ятниця", "Пт"),
    ("date:Субота", "Сб")
]
TIME_BUTTONS = [
    ("time:09:00–12:00", "09:00–12:00"),
    ("time:12:00–15:00", "12:00–15:00"),
    ("time:15:00–18:00", "15:00–18:00"),
    ("time:18:00–21:00", "18:00–21:00")
]
NAV_BUTTONS = [
    ("other_questions", "💬 Інші питання"),
    ("manager", "📞 Зв'язатися з менеджером")
]


def buttons(*items):
    return {"type": "buttons", "items": [{"id": item[0], "label": item[1]} for item in items]}


def answer(text, state, *items, **extra):
    result = {
        "response": text,
        "message": text,
        "state": state,
        "buttons": [{"id": item[0], "text": item[1]} for item in items],
        "actions": buttons(*items)
    }
    result.update(extra)
    return result


def normalize_phone(text):
    match = re.search(r"(?:\+?38)?[\s().-]*0?\d(?:[\s().-]*\d){8}", text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group())
    if len(digits) == 10 and digits.startswith("0"):
        digits = "38" + digits
    elif len(digits) == 12 and digits.startswith("380"):
        pass
    else:
        return None
    return "+" + digits


def extract_age(text):
    match = re.search(r"(?<!\d)([6-9]|1[0-8])(?!\d)", text)
    return int(match.group(1)) if match else None


def detect_course(text):
    value = text.lower()
    if value.strip() in {"ai", "ші"}:
        return "ai"
    current_aliases = {
        "photoshop": ["photoshop", "фотошоп", "малю", "ілюстрац", "обробк", "фото", "колаж"],
        "after_effects": ["after effects", "aftereffects", "афтер ефект", "афтерефект", "моушн", "анімац", "відеоефект"],
        "ai": ["штучн", "chatgpt", " ai", "ai ", "ші", "нейромереж", "генератив"],
        "digital_design": ["цифровий дизайн", "цифрового дизайну", "графічн", "дизайн", "design", "макет", "типограф"]
    }
    for course_id, words in current_aliases.items():
        if any(word in value for word in words):
            return course_id

    return None


def course_summary(course_id, include_price=False):
    course = COURSES[course_id]
    text = f"{course['name']} — {', '.join(course['topics'][:5])}.\n\nРезультат: {course['result']}."
    if include_price:
        prices = []
        if course.get("group_price"):
            prices.append(f"групові — {course['group_price']} грн/заняття")
        if course.get("individual_price"):
            prices.append(f"індивідуальні — {course['individual_price']} грн/заняття")
        text += "\n\nВартість: " + "; ".join(prices) + "."
    return text


def confirmation_text(state):
    return (
        "Перевірте заявку 👇\n\n"
        f"👦 Дитина: {state['child_name']}\n"
        f"🎂 Вік: {state['child_age']} років\n"
        f"🎓 Напрям: {COURSES[state['selected_course']]['name']}\n"
        f"📅 Бажаний день: {state['preferred_date']}\n"
        f"🕐 Бажаний час: {state['preferred_time']}\n"
        f"📞 Телефон: {state['parent_phone']}\n\nВсе правильно?"
    )


def manager_response(state_name="MANAGER_REQUEST"):
    return answer(
        f"Менеджер ItEnAi School\n\n📞 {PHONE}\n\nНатисніть на номер, щоб зателефонувати, або залиште свій телефон — менеджер зв'яжеться з Вами.",
        state_name,
        ("tel:+380931480343", "📞 Зателефонувати"),
        ("leave_phone", "☎️ Залишити мій номер"),
        ("back", "↩️ Повернутися до чату")
    )


def handle_chat(session_id, message, source="website_chat"):
    text = message.strip()
    lower = text.lower()
    state = get_conversation_state(session_id)
    current = state["state"]
    phone = normalize_phone(text)

    price_words = [
        "ціна", "ціни", "вартість", "коштує", "коштують",
        "скільки кошту", "оплата", "грн", "гривень"
    ]
    if any(word in lower for word in price_words):
        return answer(
            "Вартість одного заняття:\n\n"
            "👤 Індивідуальне заняття — 450 грн.\n"
            "👥 Заняття в мінігрупі до 4 учнів — 250 грн з учня.\n\n"
            "Бажаєте записатися на пробне заняття?",
            current,
            ("trial", "✅ Записатися на пробне"),
            ("manager", "📞 Зв'язатися з менеджером")
        )

    course_list_phrases = [
        "про курс", "про курси", "які курси", "які є курси",
        "список курсів", "напрями", "які напрями", "що є"
    ]
    if lower in {"ask", "курс", "курси"} or any(phrase in lower for phrase in course_list_phrases):
        return answer(
            "У ItEnAi School є чотири напрями:\n\n"
            "🎨 Adobe Photoshop — цифрове малювання, ілюстрації та обробка фото.\n"
            "🎬 Adobe After Effects — анімація, моушн-дизайн і візуальні ефекти.\n"
            "🤖 Штучний інтелект — ChatGPT, нейромережі та творчі AI-проєкти.\n"
            "✨ Цифровий дизайн — композиція, колір, типографіка та створення макетів.\n\n"
            "Оберіть напрям, про який хочете дізнатися більше:",
            current,
            *(COURSE_BUTTONS + NAV_BUTTONS)
        )

    if lower == "other_questions":
        update_conversation_state(session_id, state="AI_QUESTIONS")
        return answer(
            "Поставте будь-яке запитання про ItEnAi School або наші курси. Після консультації можна повернутися до анкети.",
            "AI_QUESTIONS",
            ("trial", "📝 Повернутися до запису"),
            ("manager", "📞 Зв'язатися з менеджером")
        )

    if lower == "course_selection":
        update_conversation_state(session_id, state="ASKING_AGE")
        return answer("Оберіть точний вік дитини:", "ASKING_AGE", *(AGE_BUTTONS + NAV_BUTTONS))

    if current == "AI_QUESTIONS":
        if lower in {"trial", "повернутися до запису"}:
            update_conversation_state(session_id, state="ASKING_CHILD_NAME")
            return answer("Як звати дитину?", "ASKING_CHILD_NAME", *NAV_BUTTONS)
        return answer("", "AI_QUESTIONS", ("trial", "📝 Повернутися до запису"), ("manager", "📞 Зв'язатися з менеджером"), needs_ai=True)

    manager_words = ["менеджер", "оператор", "людин", "адміністратор", "дайте номер", "зв'язатися", "зв’язатися", "консультац"]
    if any(word in lower for word in manager_words) or lower == "manager":
        if phone:
            state = update_conversation_state(session_id, parent_phone=phone, pending_callback=1, state="CONFIRMING_CALLBACK")
            return answer(f"Передати номер {phone} менеджеру ItEnAi School?", state["state"], ("confirm_callback", "✅ Так, передати"), ("manager", "❌ Ні"))
        update_conversation_state(session_id, state="MANAGER_REQUEST")
        return manager_response()

    if current == "MANAGER_REQUEST":
        if lower in {"leave_phone", "залишити мій номер"}:
            update_conversation_state(session_id, state="ASKING_CALLBACK_PHONE", pending_callback=1)
            return answer("Напишіть, будь ласка, номер телефону — менеджер зв'яжеться з Вами.", "ASKING_CALLBACK_PHONE")
        if lower == "back":
            update_conversation_state(session_id, state="IDLE")
            return answer("Повертаємося до консультації 😊 Скільки років дитині?", "ASKING_AGE", ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_CALLBACK_PHONE":
        if not phone:
            return answer("Не вдалося розпізнати номер. Напишіть його, наприклад: 093 148 03 43.", current)
        update_conversation_state(session_id, parent_phone=phone, state="CONFIRMING_CALLBACK")
        return answer(f"Передати номер {phone} менеджеру ItEnAi School?", "CONFIRMING_CALLBACK", ("confirm_callback", "✅ Так, передати"), ("manager", "❌ Ні"))

    if current == "CONFIRMING_CALLBACK" and lower in {"confirm_callback", "так", "підтвердити", "да"}:
        token = state.get("confirmation_token") or str(uuid4())
        state = update_conversation_state(session_id, confirmation_token=token)
        lead_code, _ = create_trial_lead(session_id, token, state, source, manager_callback=1)
        update_conversation_state(session_id, state="APPLICATION_CREATED", pending_callback=0)
        return answer(f"✅ Запит передано менеджеру. Номер звернення: {lead_code}. Ми зв'яжемося з Вами найближчим часом.", "APPLICATION_CREATED", ("manager", "📞 Зв'язатися з менеджером"), lead_id=lead_code)

    if lower in {"trial", "записатися", "так, записатися", "хочу записатися"} or (current == "OFFERING_TRIAL" and lower in {"так", "да", "хочу"}):
        next_state = "ASKING_CHILD_NAME" if not state.get("child_name") else "ASKING_CHILD_AGE" if not state.get("child_age") else "ASKING_COURSE" if not state.get("selected_course") else "ASKING_DATE"
        update_conversation_state(session_id, state=next_state)
        prompts = {"ASKING_CHILD_NAME": "Супер 🚀 Як звати дитину?", "ASKING_CHILD_AGE": "Скільки років дитині?", "ASKING_COURSE": "Який напрям обираємо?", "ASKING_DATE": "Який день Вам буде зручний?"}
        step_buttons = AGE_BUTTONS + NAV_BUTTONS if next_state == "ASKING_CHILD_AGE" else COURSE_BUTTONS + NAV_BUTTONS if next_state == "ASKING_COURSE" else DAY_BUTTONS + NAV_BUTTONS if next_state == "ASKING_DATE" else NAV_BUTTONS
        return answer(prompts[next_state], next_state, *step_buttons)

    if current == "ASKING_CHILD_NAME":
        name = re.sub(r"[^A-Za-zА-Яа-яІіЇїЄєҐґ'’ -]", "", text).strip().title()
        if len(name) < 2:
            return answer("Напишіть, будь ласка, ім'я дитини.", current)
        next_state = "ASKING_CHILD_AGE" if not state.get("child_age") else "ASKING_COURSE" if not state.get("selected_course") else "ASKING_DATE"
        state = update_conversation_state(session_id, child_name=name, state=next_state)
        question = {"ASKING_CHILD_AGE": "Оберіть точний вік дитини:", "ASKING_COURSE": "Оберіть напрям:", "ASKING_DATE": "Оберіть бажаний день:"}[next_state]
        step_buttons = (AGE_BUTTONS if next_state == "ASKING_CHILD_AGE" else COURSE_BUTTONS if next_state == "ASKING_COURSE" else DAY_BUTTONS) + NAV_BUTTONS
        return answer(question, state["state"], *step_buttons)

    if current in {"IDLE", "ASKING_AGE"}:
        age = extract_age(text)
        course_id = detect_course(text)
        if age:
            state = update_conversation_state(session_id, child_age=age, selected_course=course_id or state.get("selected_course"), state="ASKING_INTERESTS")
            return answer("Чудово 😊 А що дитині найбільше подобається?", "ASKING_INTERESTS", *(INTEREST_BUTTONS + NAV_BUTTONS))
        if course_id:
            state = update_conversation_state(session_id, selected_course=course_id, state="COURSE_INFO")
            price = any(word in lower for word in ["ціна", "вартість", "скільки"])
            return answer(course_summary(course_id, price) + "\n\nСкільки років дитині?", "ASKING_AGE", ("manager", "📞 Зв'язатися з менеджером"))
        update_conversation_state(session_id, state="ASKING_AGE")
        return answer("Вітаю 👋 Можна пройти короткий підбір курсу або одразу заповнити заявку на пробне заняття.", "ASKING_AGE", ("trial", "📝 Записатися на пробне"), ("course_selection", "🎓 Підібрати напрям"), *NAV_BUTTONS)

    if current == "ASKING_CHILD_AGE":
        age = extract_age(text)
        if not age:
            return answer("Вкажіть, будь ласка, вік дитини від 6 до 18 років.", current)
        state = update_conversation_state(session_id, child_age=age, state="ASKING_DATE" if state.get("selected_course") else "ASKING_COURSE")
        return answer("Оберіть бажаний день:" if state["state"] == "ASKING_DATE" else "Оберіть напрям:", state["state"], *((DAY_BUTTONS if state["state"] == "ASKING_DATE" else COURSE_BUTTONS) + NAV_BUTTONS))

    if current == "ASKING_COURSE":
        course_id = detect_course(text)
        if not course_id:
            return answer("Оберіть один із доступних напрямів:", current, *(COURSE_BUTTONS + NAV_BUTTONS))
        update_conversation_state(session_id, selected_course=course_id, state="ASKING_DATE")
        return answer("Оберіть бажаний день:", "ASKING_DATE", *(DAY_BUTTONS + NAV_BUTTONS))

    if current == "ASKING_INTERESTS":
        if lower in {"unsure", "ще не визначились", "не знаю"}:
            return answer(
                "Нічого страшного 😊 Що дитина частіше обирає у вільний час?",
                current,
                ("games", "🎮 Грати в ігри"),
                ("ai", "🤖 Експериментувати з AI"),
                ("design", "🎨 Малювати або створювати"),
                ("blogging", "🎥 Дивитися чи знімати відео"),
                ("computer", "🖥 Освоїти комп'ютер"),
                ("manager", "📞 Порадитися з менеджером")
            )
        course_id = detect_course(text)
        if not course_id:
            return answer("Підкажіть, що ближче дитині: Photoshop, After Effects, штучний інтелект чи цифровий дизайн?", current, *INTEREST_BUTTONS)
        state = update_conversation_state(session_id, interests=text, selected_course=course_id, state="OFFERING_TRIAL")
        return answer(f"Я рекомендую {course_summary(course_id)}\n\nХочете підібрати день і час для пробного заняття?", "OFFERING_TRIAL", ("trial", "✅ Так, записатися"), ("ask", "💬 Спочатку хочу запитати"), ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_DATE":
        if lower not in {"date:п’ятниця", "date:субота"}:
            return answer("Пробні заняття доступні у п’ятницю або суботу. Оберіть день:", current, *(DAY_BUTTONS + NAV_BUTTONS))
        selected_date = text.split(":", 1)[1]
        state = update_conversation_state(session_id, preferred_date=selected_date, state="ASKING_TIME")
        return answer("Оберіть приблизний зручний час:", "ASKING_TIME", *(TIME_BUTTONS + NAV_BUTTONS))

    if current == "ASKING_TIME":
        selected_time = text.split(":", 1)[1] if lower.startswith("time:") else text
        state = update_conversation_state(session_id, preferred_time=selected_time, state="ASKING_PHONE")
        return answer("Залиште, будь ласка, номер телефону одного з батьків. Менеджер перевірить вільний час і підтвердить заняття.", "ASKING_PHONE", ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_PHONE":
        if not phone:
            return answer("Не вдалося розпізнати номер. Напишіть його, наприклад: +380 93 148 03 43.", current)
        token = str(uuid4())
        state = update_conversation_state(session_id, parent_phone=phone, confirmation_token=token, state="CONFIRMING_APPLICATION")
        return answer(confirmation_text(state), "CONFIRMING_APPLICATION", ("confirm", "✅ Підтвердити запис"), ("edit", "✏️ Змінити дані"), ("cancel", "❌ Скасувати"))

    if current == "CONFIRMING_APPLICATION":
        if lower in {"confirm", "підтвердити", "так", "все правильно", "да"}:
            lead_code, _ = create_trial_lead(session_id, state["confirmation_token"], state, source)
            update_conversation_state(session_id, state="APPLICATION_CREATED")
            return answer(f"✅ Готово! Заявку {lead_code} отримано. Менеджер ItEnAi School перевірить можливий час і зв'яжеться з Вами для підтвердження заняття 🚀", "APPLICATION_CREATED", ("manager", "📞 Зв'язатися з менеджером"), lead_id=lead_code)
        if lower in {"cancel", "скасувати", "ні"}:
            update_conversation_state(session_id, state="IDLE", confirmation_token=None)
            return answer("Заявку скасовано. Якщо захочете повернутися — я допоможу 😊", "IDLE", ("manager", "📞 Зв'язатися з менеджером"))
        if lower in {"edit", "змінити", "редагувати"}:
            update_conversation_state(session_id, state="ASKING_CHILD_NAME")
            return answer("Добре, почнемо уточнення. Як звати дитину?", "ASKING_CHILD_NAME")
        return answer(confirmation_text(state), current, ("confirm", "✅ Підтвердити запис"), ("edit", "✏️ Змінити дані"), ("cancel", "❌ Скасувати"))

    course_id = detect_course(text)
    if course_id:
        return answer(course_summary(course_id, any(word in lower for word in ["ціна", "вартість"])), current, ("trial", "✅ Записатися на пробне"), ("manager", "📞 Зв'язатися з менеджером"))
    return answer("Можу розповісти про курс або допомогти із записом на пробне заняття. Що Вас цікавить?", current, ("trial", "✅ Записатися на пробне"), ("manager", "📞 Зв'язатися з менеджером"))
