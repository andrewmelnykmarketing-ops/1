import os
import random
import socket
from datetime import time
from collections import defaultdict
from zoneinfo import ZoneInfo

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

# Token
TOKEN = os.getenv("BOT_TOKEN")

# Port for Render
PORT = int(os.getenv("PORT", "10000"))

# Subscribed users
subscribed_users = set()

# Daily state
user_state = defaultdict(lambda: {"has_taken": False, "reminders_sent": 0})

# Wishes
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


def bind_port():
    """Fake listener for Render."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.listen(5)
    print(f"Listening on port {PORT}")
    return s


def pill_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Так", callback_data="pill_taken")]]
    )


# ------------------ HANDLERS ------------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    subscribed_users.add(user_id)

    await update.message.reply_text(
        "Привіт!\n"
        "Я буду щодня нагадувати тобі про таблетку 💊\n"
        "об 11:00 (за іспанським часом)"
    )


async def say_random_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wish = random.choice(good_wishes)
    await update.message.reply_text(wish)


async def testpill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Тестовий режим: нагадування кожну 1 хвилину 💊")
    await send_daily_first_reminder(context, test_mode=True)


# ------------------ REMINDER LOGIC ------------------


async def send_daily_first_reminder(context: ContextTypes.DEFAULT_TYPE, test_mode=False):
    print("Running job, test_mode =", test_mode)

    for user_id in list(subscribed_users):
        user_state[user_id]["has_taken"] = False
        user_state[user_id]["reminders_sent"] = 0

        await context.bot.send_message(
            chat_id=user_id,
            text="Ти випила таблетку?",
            reply_markup=pill_keyboard(),
        )

        interval = 60 if test_mode else 20 * 60
        first_delay = interval

        context.job_queue.run_repeating(
            pill_followup_reminder,
            interval=interval,
            first=first_delay,
            name=f"reminder_{user_id}",
            data={"user_id": user_id},
        )


async def pill_followup_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_id = job.data["user_id"]
    state = user_state[user_id]

    if state["has_taken"]:
        job.schedule_removal()
        return

    if state["reminders_sent"] >= 12:
        job.schedule_removal()
        return

    state["reminders_sent"] += 1

    await context.bot.send_message(
        chat_id=user_id,
        text="Ну шо? Випила таблетку?",
        reply_markup=pill_keyboard(),
    )


async def pill_taken_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_state[user_id]["has_taken"] = True

    await query.edit_message_text("Молодець 💊 Побачимось завтра об 11:00 😉")

    for job in context.application.job_queue.get_jobs_by_name(f"reminder_{user_id}"):
        job.schedule_removal()


# ------------------ MAIN ------------------


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing")

    listener = bind_port()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("testpill", testpill))
    app.add_handler(
        CallbackQueryHandler(pill_taken_button, pattern="^pill_taken$")
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, say_random_wish)
    )

    tz = ZoneInfo("Europe/Madrid")
    app.job_queue.run_daily(
        send_daily_first_reminder,
        time=time(hour=11, minute=0, tzinfo=tz),
        name="daily_job",
    )

    print("Bot started")
    app.run_polling()

    _ = listener


if __name__ == "__main__":
    main()
