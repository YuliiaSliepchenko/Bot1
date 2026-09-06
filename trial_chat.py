import json
import re
from pathlib import Path
from uuid import uuid4

from db import create_trial_lead, get_conversation_state, update_conversation_state


FULL_KNOWLEDGE = json.loads(
    (Path(__file__).with_name("ITENAISchool_knowledge_base_FULL.json")).read_text(encoding="utf-8")
)
COURSES = {course["id"]: course for course in FULL_KNOWLEDGE["courses"]}
COURSES["blogging_video"] = {
    "id": "blogging_video",
    "name": "📱 Блогінг + Відеомонтаж",
    "description": "Створення контенту для соціальних мереж: від ідеї та сценарію до зйомки й готового відео.",
    "program": ["ідеї та сценарії", "зйомка", "монтаж", "CapCut", "субтитри", "переходи та ефекти"],
    "result": "Власні завершені відео та контент для соціальних мереж",
}
PHONE = FULL_KNOWLEDGE["school"]["manager_phone"]
FAQ = FULL_KNOWLEDGE["faq"]

INTEREST_BUTTONS = [
    ("game_development", "🎮 Розробка ігор"),
    ("web", "🌐 Розробка сайтів"),
    ("python", "🐍 Програмування Python"),
    ("ai", "🤖 Штучний інтелект"),
    ("photoshop", "🎨 Дизайн і малювання"),
    ("blogging_video", "📱 Блогінг + монтаж"),
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
    ("manager", "📞 Зв'язатися з менеджером"),
    ("menu", "⬅️ Головне меню")
]

MAIN_MENU_BUTTONS = [
    ("course_selection", "🎓 Підібрати напрям"),
    ("trial", "🧪 Записатися на пробне"),
    ("show_courses", "📚 Програми курсів"),
    ("show_prices", "💰 Вартість"),
    ("other_questions", "🤖 Запитати AI-менеджера"),
    ("manager", "👩‍💼 Зв'язатися з менеджером"),
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
        "game_development": ["game_development", "розробк", "створ", "ігри", "ігор", "game development"],
        "minecraft_education": ["minecraft", "майнкрафт"],
        "roblox": ["roblox", "роблокс"],
        "scratch": ["scratch", "скретч"],
        "construct": ["construct"],
        "unity": ["unity", "юніті"],
        "python": ["python", "пайтон", "програмув"],
        "vibe_coding": ["vibe coding", "вайб код"],
        "web": ["web", "сайт", "html", "css", "javascript", "веб"],
        "blender": ["blender", "блендер", "3d", "3д"],
        "blogging": ["блог", "контент"],
        "blogging_video": ["blogging_video", "блогінг + монтаж", "блогінг та монтаж"],
        "computer_literacy": ["комп'ютерна грамот", "комп’ютерна грамот"],
        "english_it": ["english", "англійськ"],
        "photoshop": ["photoshop", "фотошоп", "малю", "ілюстрац", "обробк", "фото", "колаж"],
        "after_effects": ["after effects", "aftereffects", "афтер ефект", "афтерефект", "моушн", "анімац", "відеоефект"],
        "ai": ["штучн", "chatgpt", " ai", "ai ", "ші", "нейромереж", "генератив"],
        "digital_design": ["цифровий дизайн", "цифрового дизайну", "графічн", "дизайн", "design", "макет", "типограф"],
        "video_editing": ["video_editing", "відеомонтаж", "монтаж відео"]
    }
    for course_id, words in current_aliases.items():
        if any(word in value for word in words):
            return course_id

    return None


def course_summary(course_id, include_price=False):
    course = COURSES[course_id]
    program = course.get("program", course.get("topics", []))
    if isinstance(program, str):
        program_text = program
    else:
        program_text = ", ".join(program[:5])
    text = f"{course['name']} — {course.get('description', program_text)}"
    if program_text:
        text += f"\n\nНа курсі: {program_text}."
    text += f"\n\nРезультат: {course['result']}."
    if include_price:
        text += f"\n\n{FAQ['prices']}"
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


def main_menu_response(text="Оберіть, що Вас цікавить:"):
    return answer(text, "IDLE", *MAIN_MENU_BUTTONS)


def deterministic_faq(lower):
    """Return verified answers for common questions without calling the AI."""
    rules = [
        (("ціна", "ціни", "вартість", "коштує", "коштують", "скільки кошту", "оплата", "грн"), "prices"),
        (("безкоштов", "пробний безкоштов", "пробне безкоштов"), "trial"),
        (("дні пробн", "коли пробн", "день пробн", "розклад пробн"), "trial_days"),
        (("онлайн", "дистанцій"), "is_online"),
        (("формат", "індивідуаль", "мінігруп", "групов"), "formats"),
        (("без досвіду", "з нуля", "досвід"), "experience"),
        (("викладач", "вчитель", "педагог"), "teachers"),
        (("сертифікат",), "certificate"),
        (("адрес", "де знаходит", "кременчук"), "address"),
        (("контакт", "телефон", "пошта", "email"), "contacts"),
    ]
    for phrases, key in rules:
        if any(phrase in lower for phrase in phrases):
            return FAQ[key]
    return None


def handle_chat(session_id, message, source="website_chat"):
    text = message.strip()
    lower = text.lower()
    state = get_conversation_state(session_id)
    current = state["state"]
    phone = normalize_phone(text)

    action_aliases = {
        "start_trial": "trial",
        "start_course_selection": "course_selection",
        "show_prices": "prices",
        "ai_manager": "other_questions",
        "live_manager": "manager",
        "main_menu": "menu",
    }
    lower = action_aliases.get(lower, lower)

    if lower == "menu":
        update_conversation_state(session_id, state="IDLE")
        return main_menu_response()

    if lower == "show_courses":
        lower = "курси"

    if lower == "prices":
        lower = "вартість"

    booking_request_variants = {
        "запис", "записатись", "записатися", "записатися на пробне",
        "пробне", "пробне заняття", "на пробне",
        "допомогти з записом", "допомогти із записом",
        "хочу записатися", "хочу записатись", "можна записатись",
        "можна записатися", "запис на пробне"
    }
    looks_like_gibberish = bool(re.search(r"[a-zа-я]{1,2}\s+[a-zа-я]{1,2}\s+[a-zа-я]{1,2}", lower)) and not any(word in lower for word in ["курс", "курс", "пробне", "малю", "дизайн", "анімац", "штучн", "запис", "хочу", "дитина", "вік", "хто", "що"]) 
    if looks_like_gibberish:
        lower = ""

    has_booking_intent = lower in booking_request_variants or any(
        phrase in lower
        for phrase in ("хочу запис", "можна запис", "запишіть", "допоможіть запис")
    )
    if has_booking_intent:
        next_state = "ASKING_CHILD_NAME" if not state.get("child_name") else "ASKING_CHILD_AGE" if not state.get("child_age") else "ASKING_COURSE" if not state.get("selected_course") else "ASKING_DATE"
        update_conversation_state(session_id, state=next_state)
        prompts = {"ASKING_CHILD_NAME": "Супер 🚀 Як звати дитину?", "ASKING_CHILD_AGE": "Скільки років дитині?", "ASKING_COURSE": "Який напрям обираємо?", "ASKING_DATE": "Який день Вам буде зручний?"}
        step_buttons = AGE_BUTTONS + NAV_BUTTONS if next_state == "ASKING_CHILD_AGE" else COURSE_BUTTONS + NAV_BUTTONS if next_state == "ASKING_COURSE" else DAY_BUTTONS + NAV_BUTTONS if next_state == "ASKING_DATE" else NAV_BUTTONS
        return answer(prompts[next_state], next_state, *step_buttons)

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
            ("manager", "📞 Зв'язатися з менеджером"),
            ("menu", "⬅️ Головне меню")
        )

    course_list_phrases = [
        "про курс", "про курси", "які курси", "які є курси",
        "список курсів", "напрями", "які напрями", "що є"
    ]
    if lower in {"ask", "курс", "курси"} or any(phrase in lower for phrase in course_list_phrases):
        course_names = "\n".join(f"• {course['name']}" for course in COURSES.values())
        return answer(
            f"У ItEnAi School доступні такі напрями:\n\n{course_names}\n\n"
            "Оберіть напрям, про який хочете дізнатися більше:",
            current,
            *(COURSE_BUTTONS + NAV_BUTTONS)
        )

    manager_words = ["менеджер", "оператор", "людин", "адміністратор", "дайте номер", "зв'язатися", "зв’язатися", "консультац"]
    if any(word in lower for word in manager_words) or lower == "manager":
        if phone:
            state = update_conversation_state(session_id, parent_phone=phone, pending_callback=1, state="CONFIRMING_CALLBACK")
            return answer(f"Передати номер {phone} менеджеру ItEnAi School?", state["state"], ("confirm_callback", "✅ Так, передати"), ("cancel_callback", "❌ Ні"))
        update_conversation_state(session_id, state="MANAGER_REQUEST")
        return manager_response()

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

    faq_answer = deterministic_faq(lower)
    if faq_answer:
        return answer(
            faq_answer,
            current,
            ("trial", "🧪 Записатися на пробне"),
            ("menu", "⬅️ Головне меню"),
            ("manager", "📞 Зв'язатися з менеджером"),
            used_ai=False,
        )

    if current == "AI_QUESTIONS":
        if lower in {"trial", "повернутися до запису"}:
            update_conversation_state(session_id, state="ASKING_CHILD_NAME")
            return answer("Як звати дитину?", "ASKING_CHILD_NAME", *NAV_BUTTONS)
        return answer("", "AI_QUESTIONS", ("trial", "📝 Повернутися до запису"), ("manager", "📞 Зв'язатися з менеджером"), needs_ai=True, used_ai=True)

    if current == "MANAGER_REQUEST":
        if lower in {"leave_phone", "залишити мій номер"}:
            update_conversation_state(session_id, state="ASKING_CALLBACK_PHONE", pending_callback=1)
            return answer("Напишіть, будь ласка, номер телефону — менеджер зв'яжеться з Вами.", "ASKING_CALLBACK_PHONE")
        if lower == "back":
            update_conversation_state(session_id, state="IDLE")
            return main_menu_response("Повертаємося до консультації 😊")

    if current == "ASKING_CALLBACK_PHONE":
        if not phone:
            return answer("Не вдалося розпізнати номер. Напишіть його, наприклад: 093 148 03 43.", current)
        update_conversation_state(session_id, parent_phone=phone, state="CONFIRMING_CALLBACK")
        return answer(f"Передати номер {phone} менеджеру ItEnAi School?", "CONFIRMING_CALLBACK", ("confirm_callback", "✅ Так, передати"), ("cancel_callback", "❌ Ні"))

    if current == "CONFIRMING_CALLBACK" and lower in {"cancel_callback", "ні", "скасувати"}:
        update_conversation_state(session_id, state="IDLE", pending_callback=0, confirmation_token=None)
        return main_menu_response("Добре, номер не передаємо. Що Вас цікавить далі?")

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
        return main_menu_response("Вітаю 👋 Допоможу підібрати курс або записати дитину на безкоштовний пробний урок.")

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
                ("game_development", "🎮 Створювати ігри"),
                ("web", "🌐 Створювати сайти"),
                ("python", "🐍 Програмувати"),
                ("ai", "🤖 Експериментувати з AI"),
                ("photoshop", "🎨 Малювати або створювати"),
                ("blogging_video", "📱 Блогінг + монтаж відео"),
                ("manager", "📞 Порадитися з менеджером")
            )
        course_id = detect_course(text)
        if not course_id:
            return answer("Оберіть, що дитині найбільше подобається:", current, *(INTEREST_BUTTONS + NAV_BUTTONS))
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
    return main_menu_response("Можу розповісти про курс або допомогти із записом на пробне заняття. Що Вас цікавить?")
