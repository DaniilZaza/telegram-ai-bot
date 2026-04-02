import asyncio
from aiogram import Bot, Dispatcher, types
import os, requests, json

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

API_KEY = os.getenv("OPENROUTER_API_KEY")

FILES = {
    "memory": "memory.json",
    "profile": "profile.json",
    "goals": "goals.json",
    "thoughts": "thoughts.json"
}

def load(name):
    f = FILES[name]
    return json.load(open(f)) if os.path.exists(f) else {}

def save(name, data):
    json.dump(data, open(FILES[name], "w"))

data = {k: load(k) for k in FILES}

SYSTEM = {
    "role": "system",
    "content": """
Ты — умный, спокойный и полезный ассистент.

Правила:
- отвечай естественно, как человек
- не переспрашивай без причины
- не усложняй
- если вопрос простой — отвечай просто
- если сложный — объясняй структурно
"""
}

def build_context(uid):
    return f"""
Профиль: {data['profile'].get(uid, [])[:3]}
Цели: {data['goals'].get(uid, [])[:3]}
"""

@dp.message()
async def handle(message: types.Message):
    uid = str(message.from_user.id)
    text = message.text

    for k in data:
        if uid not in data[k]:
            data[k][uid] = []

    # сохраняем факты
    if text.lower().startswith("я "):
        data["profile"][uid].append(text)
        save("profile", data["profile"])
        await message.answer("Запомнил")
        return

    if text.lower().startswith("цель"):
        data["goals"][uid].append(text.replace("цель", "").strip())
        save("goals", data["goals"])
        await message.answer("Цель добавлена")
        return

    if text.lower().startswith("мысль"):
        data["thoughts"][uid].append(text.replace("мысль", "").strip())
        save("thoughts", data["thoughts"])
        await message.answer("Сохранил")
        return

    # память диалога
    if uid not in data["memory"]:
        data["memory"][uid] = []

    messages = [SYSTEM]

    # добавляем контекст как system
    context = build_context(uid)
    messages.append({"role": "system", "content": f"Контекст:\n{context}"})

    # добавляем последние сообщения
    messages += data["memory"][uid][-6:]

    # новое сообщение
    messages.append({"role": "user", "content": text})

    # запрос
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "openai/gpt-4o-mini",
            "messages": messages
        }
    )

    reply = response.json()["choices"][0]["message"]["content"]

    # сохраняем историю
    data["memory"][uid].append({"role": "user", "content": text})
    data["memory"][uid].append({"role": "assistant", "content": reply})

    data["memory"][uid] = data["memory"][uid][-10:]

    save("memory", data["memory"])

    await message.answer(reply)

async def main():
    await dp.start_polling(bot)

asyncio.run(main())
