import asyncio
from aiogram import Bot, Dispatcher, types
import os
import requests

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

user_history = {}

API_KEY = os.getenv("OPENROUTER_API_KEY")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in user_history:
        user_history[user_id] = []

    user_history[user_id].append({"role": "user", "content": text})

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-3.5-turbo",
            "messages": user_history[user_id]
        }
    )

    reply = response.json()["choices"][0]["message"]["content"]

    user_history[user_id].append({"role": "assistant", "content": reply})

    await message.answer(reply)

async def main():
    await dp.start_polling(bot)

asyncio.run(main())
