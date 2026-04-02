import asyncio
from aiogram import Bot, Dispatcher, types
from openai import OpenAI
import os

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

user_history = {}

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in user_history:
        user_history[user_id] = []

    user_history[user_id].append({"role": "user", "content": text})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=user_history[user_id]
    )

    reply = response.choices[0].message.content

    user_history[user_id].append({"role": "assistant", "content": reply})

    await message.answer(reply)

async def main():
    await dp.start_polling(bot)

asyncio.run(main())
