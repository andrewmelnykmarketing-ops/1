import os
import random
import socket
from datetime import time
from collections import defaultdict
from zoneinfo import ZoneInfo  # для коректної таймзони Europe/Madrid

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Токен бота з Environment
TOKEN = os.getenv("BOT_TOKEN")

# Порт, який очікує Render (для фейкового лістенера)
PORT = int(os.getenv("PORT", "10000"))

# Хто підписаний на нагадування
subscribed_users: set[int] = set()

# Стан по кожному користувачу на день
# has_taken – чи натиснули "Так" сьогодні
# reminders_sent – скільки нагадувань уже було
user_state = defaultdict(lambda: {"has_taken": False, "reminders_sent": 0})

# Список побажань
good_wishes = [
    "Гарного тобі дня 🌿",
    "Хай сьогодні буде світло всередині",
    "Нехай думки будуть тихими і спокійними",
    "Хай твоє серце відчує тепло",
    "Бажаю тобі ясності",
    "Нехай усе складеться найкращим чином",
    "Хай сьогодні буде легко",
    "Бажаю рівноваги",
    "Хай день принесе приємні новини",
    "Нехай всередині буде тиша",
    "Бажаю добрих сил",
    "Хай у твоєму просторі буде мир",
    "Нехай усе буде м’яко й спокійно",
    "Бажаю теплих людей поруч",
    "Хай прийде відповідь на те, що шукаєш",
    "Нехай всесвіт тримає тебе ніжно",
    "Бажаю відчути себе впевнено",
    "Хай твоє серце трохи відпочине",
    "Бажаю внутрішнього затишку",
    "Нехай день буде добрим до тебе",
    "Хай прийде легкість у думки",
    "Бажаю світлого настрою",
    "Нехай усе непотрібне відпаде саме",
    "Хай буде спокій у твоєму домі",
    "Бажаю гармонії",
    "Хай сьогоднішній день принесе усмішку",
    "Нехай знайдеться щось добре навіть у дрібницях",
    "Бажаю тихої радості",
    "Хай тебе огорне спокій",
    "Нехай сили приходять рівно настільки, наскільки потрібно",
    "Бажаю внутрішньої опори",
    "Хай серце стане теплішим",
    "Нехай думки будуть ясними",
    "Бажаю приємної миті тиші",
    "Хай у тебе все буде вчасно",
    "Бажаю добрих емоцій",
    "Нехай день буде лагідним",
    "Хай твої кроки будуть впевненими",
    "Нехай спокій прийде без зусиль",
    "Бажаю бути в ресурсі",
    "Хай всередині стане світліше",
    "Нехай тебе оточує м’якість",
    "Бажаю приємного відчуття рівноваги",
    "Хай твоє серце не поспішатиме",
    "Нехай турбота знайде тебе",
    "Бажаю теплого моменту для себе",
    "Хай прийде відповідь у потрібний момент",
    "Нехай день повернеться до тебе добром",
    "Бажаю відчути підтримку всередині",
    "Хай у тобі живе спокій",
]


def pill_keyboard() -> InlineKeyboardMarkup:
    """Кнопка 'Так' під нагадуванням."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Так", callback_data="pill_taken")]]
    )


def bind_port():
    """
    Фейковий лістенер для Render – просто відкриває порт.
    Щоб Web Service не падав з 'port scan timeout'.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.listen(5)
    print(f"Listening on port {PORT} for Render health checks")
    return s


# --------------- ХЕНДЛЕРИ КОМАНД -----------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start – підписка на нагадування."""
    if update.message is None:
        return

    user_id = update.effective_user.id
    subscribed_users.add(user_id)

    await update.message.reply_text(
        "Привіт! Я буду щодня о 11:00 (за твоїм іспанським часом) "
        "нагадувати тобі про таблетку 💊\n"
        "Для тесту можеш використати команду /testpill."
    )


async def say_random_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Рандомне побажання на будь-яке текстове повідомлення."""
    if update.message is None:
        return

    wish = random.choice(good_wishes)
    await update.message.reply_text(wish)


async def testpill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /testpill – запускає сценарій з таблеткою в тест-режимі:
    нагадування кожну 1 хвилину (замість 20 хв).
    """
    if update.message is None:
        return

    await update.message.reply_text(
        "Тестовий режим 💊 Нагадування кожну 1 хвилину."
    )
    await send_daily_first_reminder(context, test_mode=True)


# --------------- ЛОГІКА НАГАДУВАНЬ -----------------


async def send_daily_first_reminder(
    context: ContextTypes.DEFAULT_TYPE,
    test_mode: bool = False,
):
    """
    Перший щоденний (або тестовий) запуск:
    – скидаємо стан
    – шлемо 'Ти випила таблетку?'
    – запускаємо повторні нагадування
    test_mode = False → кожні 20 хв
    test_mode = True → кожну 1 хв
    """
    print("Running daily job (test_mode =", test_mode, ")")

    for user_id in list(subscribed_users):
        # новий день / новий тестовий запуск
        user_state[user_id]["has_taken"] = False
        user_state[user_id]["reminders_sent"] = 0

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Ти випила таблетку?",
                reply_markup=pill_keyboard(),
            )
        except Exception as e:
            print(f"Error sending first reminder to {user_id}: {e}")
            continue

        # інтервали
        interval_seconds = 60 if test_mode else 20 * 60
        first_delay = 60 if test_mode else 20 * 60

        context.job_queue.run_repeating(
            pill_followup_reminder,
            interval=interval_seconds,
            first=first_delay,
            name=f"reminder_{user_id}",
            data={"user_id": user_id},
        )


async def pill_followup_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Нагадування:
    – якщо натиснули "Так" або 12 разів – стоп
    – інакше 'Ну шо? Випила таблетку?'
    """
    job = context.job
    if job is None:
        return

    user_id = job.data["user_id"]
    state = user_state[user_id]

    if state["has_taken"]:
        job.schedule_removal()
        return

    if state["reminders_sent"] >= 12:
        job.schedule_removal()
        return

    state["reminders_sent"] += 1

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="Ну шо? Випила таблетку?",
            reply_markup=pill_keyboard(),
        )
    except Exception as e:
        print(f"Error sending followup to {user_id}: {e}")
        job.schedule_removal()


async def pill_taken_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Натискання кнопки "Так":
    – ставимо has_taken = True
    – обнуляємо лічильник
    – прибираємо всі jobs з нагадуваннями для цього юзера
    """
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    user_id = query.from_user.id
    user_state[user_id]["has_taken"] = True
    user_state[user_id]["reminders_sent"] = 0

    try:
        await query.edit_message_text(
            "Молодець 💊 Побачимось завтра о 11:00 😉"
        )
    except Exception as e:
        print(f"Error editing message for {user_id}: {e}")

    for job in context.application.job_queue.get_jobs_by_name(
        f"reminder_{user_id}"
    ):
        job.schedule_removal()


# --------------- MAIN -----------------


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN env var is not set")

    # відкриваємо порт для Render (щоб Web Service був задоволений)
    listener = bind_port()

    app = ApplicationBuilder().token(TOKEN).build()

    # Команди
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("testpill", testpill))

    # Кнопка "Так"
    app.add_handler(
        CallbackQueryHandler(pill_taken_button, pattern="^pill_taken$")
    )

    # Рандомне побажання на будь-який текст, що не є командою
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, say_random_wish)
    )

    # Таймзона – Іспанія (автоматично CET/CEST)
    tz = ZoneInfo("Europe/Madrid")

    # Щоденне нагадування о 11:00 за локальним часом Іспанії
    app.job_queue.run_daily(
        send_daily_first_reminder,
        time=time(hour=11, minute=0, tzinfo=tz),
        name="daily_pill_job",
    )

    print("Bot started")
    app.run_polling()

    # щоб змінна listener не вважалась "невикористаною"
    _ = listener


if __name__ == "__main__":
    main()
