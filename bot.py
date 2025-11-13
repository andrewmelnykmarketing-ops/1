# Simple test bot – send "Привіт" to all subscribed users

import json
import os
from telegram import Bot

# >>> встав свій токен <<<
BOT_TOKEN = "8513409579:AAE9yAxqjq6_QekGvb30GRKezOW5-uKMFrc"

DATA_FILE = "users.json"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}


def main():
    bot = Bot(token=BOT_TOKEN)
    data = load_data()

    print("Sending messages to:", data.keys())

    for user_id in data.keys():
        try:
            bot.send_message(chat_id=int(user_id), text="Привіт 👋 (тестове повідомлення)")
            print("OK →", user_id)
        except Exception as e:
            print("ERR →", user_id, str(e))


if __name__ == "__main__":
    main()
