# Pill reminder bot – v2 (token inside code)

import os
import json
import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# ВСТАВ СВОЙ ТОКЕН ТУТ
BOT_TOKEN = "8513409579:AAE9yAxqjq6_QekGvb30GRKezOW5-uKMFrc"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

DATA_FILE = "users.json"
TZ = ZoneInfo("Europe/Madrid")  # CET/CEST


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "confirmed_today": False,
            "last_reminder_time": None
        }
        save_data(data)

    await update.message.reply_text(
        "Гаразд, я буду нагадувати щодня о 11:00 CET 😊"
    )


async def send_daily_prompt(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Так", callback_data="confirm_yes")]
    ])

    for user_id in data.keys():
        data[user_id]["confirmed_today"] = False
        data[user_id]["last_reminder_time"] = None
        await context.bot.send_message(
            chat_id=int(user_id),
            text="Ти прийняла таблетку?",
            reply_markup=keyboard
        )

    save_data(data)


async def reminder_loop(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    end_of_day = now.replace(hour=23, minute=0, second=0, microsecond=0)

    if now > end_of_day:
        return

    data = load_data()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Так", callback_data="confirm_yes")]
    ])

    for user_id, info in data.items():
        if not info["confirmed_today"]:
            await context.bot.send_message(
                chat_id=int(user_id),
                text="Нагадування: ти прийняла таблетку?",
                reply_markup=keyboard
            )

    save_data(data)


async def reset_day(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    for user_id in data.keys():
        data[user_id]["confirmed_today"] = False
        data[user_id]["last_reminder_time"] = None
    save_data(data)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    data = load_data()

    data[user_id]["confirmed_today"] = True
    save_data(data)

    await query.edit_message_text("Добре! На сьогодні більше нагадувань не буде 👍")


async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    job_queue = app.job_queue

    job_queue.run_daily(
        send_daily_prompt,
        time=time(hour=11, minute=0, tzinfo=TZ)
    )

    job_queue.run_daily(
        reset_day,
        time=time(hour=0, minute=0, tzinfo=TZ)
    )

    job_queue.run_repeating(
        reminder_loop,
        interval=900,
        first=0
    )

    print("Bot started...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
