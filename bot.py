import asyncio
from aiogram import Bot, Dispatcher, types
import os
import requests
import json

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

API_KEY = os.getenv("OPENROUTER_API_KEY")

# файл для памяти
MEMORY_FILE = "memory.json"

# загружаем память
if os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "r") as f:
        user_history = json.load(f)
else:
    user_history = {}

# системный промпт (личность)
SYSTEM_PROMPT = {
    "role": "system",
    "content": "Ты личный ассистент пользователя. Помогаешь с жизнью, задачами, мыслями, поддержкой и планированием. Отвечаешь понятно, по делу и иногда задаёшь уточняющие вопросы."
}

def save_memory():
    with open(MEMORY_FILE, "w") as f:
        json.dump(user_history, f)

@dp.message()
async def handle_message(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text

    # команда очистки
    if text == "/clear":
        user_history[user_id] = []
        save_memory()
        await message.answer("Память очищена 🧹")
        return

    if user_id not in user_history:
        user_history[user_id] = [SYSTEM_PROMPT]

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
    save_memory()

    await message.answer(reply)

async def main():
    await dp.start_polling(bot)

asyncio.run(main())
