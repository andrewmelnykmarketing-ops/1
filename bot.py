import os
from datetime import time
from zoneinfo import ZoneInfo
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

# хто підписався на нагадування
subscribed_users = set()

# стан по кожному юзеру на сьогодні
# has_taken – чи натиснули "Так" сьогодні
# reminders_sent – скільки 20-хв нагадувань уже було
user_state = defaultdict(lambda: {"has_taken": False, "reminders_sent": 0})


def pill_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Так", callback_data="pill_taken")]]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Коли юзер пише /start – додаємо його в список і пояснюємо логіку."""
    user_id = update.effective_user.id
    subscribed_users.add(user_id)

    await update.message.reply_text(
        "Привіт! Я буду щодня о 11:00 нагадувати тобі про таблетку 💊"
    )


async def say_hi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просто відповідь на будь-яке текстове повідомлення (можеш прибрати)."""
    if update.message:
        await update.message.reply_text("привіт")


async def send_daily_first_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Щоденний тригер о 11:00 CET:
    – скидаємо стан на сьогодні
    – шлемо перше повідомлення "Ти випила таблетку?"
    – запускаємо 20-хв нагадування для кожного юзера
    """
    print("Running daily 11:00 CET job")

    for user_id in list(subscribed_users):
        # скидаємо стан на новий день
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

        # запускаємо нагадування кожні 20 хв, максимум 12 разів
        # перше – через 20 хв після 11:00
        context.job_queue.run_repeating(
            pill_followup_reminder,
            interval=20 * 60,           # 20 хв у секундах
            first=20 * 60,              # перше нагадування через 20 хв
            name=f"reminder_{user_id}",
            data={"user_id": user_id},
        )


async def pill_followup_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Нагадування кожні 20 хв:
    – якщо натиснули "Так" або вже 12 разів – зупиняємо job
    – інакше шлемо "Ну шо? Випила таблетку?"
    """
    job = context.job
    user_id = job.data["user_id"]

    state = user_state[user_id]
    if state["has_taken"]:
        # вже відмітила – на сьогодні вистачить
        job.schedule_removal()
        return

    if state["reminders_sent"] >= 12:
        # досягли ліміту 12 нагадувань
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
    Обробка натискання кнопки "Так":
    – ставимо has_taken = True
    – обнуляємо лічильник нагадувань
    – прибираємо всі jobs з нагадуваннями для цього юзера
    """
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_state[user_id]["has_taken"] = True
    user_state[user_id]["reminders_sent"] = 0

    # редагуємо останнє повідомлення
    try:
        await query.edit_message_text(
            "Молодець 💊 Побачимось завтра о 11:00 😉"
        )
    except Exception as e:
        print(f"Error editing message for {user_id}: {e}")

    # зупиняємо всі jobs з нагадуваннями для цього юзера
    for job in context.job_queue.get_jobs_by_name(f"reminder_{user_id}"):
        job.schedule_removal()


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # хендлери
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        CallbackQueryHandler(pill_taken_button, pattern="^pill_taken$")
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, say_hi))

    # таймзона – Іспанія (CET/CEST, автоматично з літнім часом)
    tz = ZoneInfo("Europe/Madrid")

    # щоденний джоб о 11:00 по цій таймзоні
    app.job_queue.run_daily(
        send_daily_first_reminder,
        time=time(hour=11, minute=0, tzinfo=tz),
        name="daily_pill_job",
    )

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
