import asyncio
from aiogram import Bot, Dispatcher, types
import os, requests, json, time, random

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher()

API_KEY = os.getenv("OPENROUTER_API_KEY")

FILES = {
    "memory": "memory.json",
    "profile": "profile.json",
    "goals": "goals.json",
    "tasks": "tasks.json",
    "habits": "habits.json",
    "thoughts": "thoughts.json"
}

def load(name):
    f = FILES[name]
    return json.load(open(f)) if os.path.exists(f) else {}

def save(name, data):
    json.dump(data, open(FILES[name], "w"))

data = {k: load(k) for k in FILES}

def search_memory(uid, text):
    memories = data["thoughts"].get(uid, [])
    relevant = []

    for m in memories:
        if any(word in m for word in text.split()):
            relevant.append(m)

    return relevant[:5]

SYSTEM = {
    "role": "system",
    "content": """Ты — личный ассистент и коуч. Помогаешь расти, анализируешь и направляешь."""
}

def build_context(uid):
    return f"""
Профиль: {data['profile'].get(uid, [])}
Цели: {data['goals'].get(uid, [])}
Задачи: {data['tasks'].get(uid, [])}
Привычки: {data['habits'].get(uid, [])}
Мысли: {data['thoughts'].get(uid, [])}
"""

async def proactive_loop():
    while True:
        await asyncio.sleep(3600)

        for uid in data["profile"]:
            msg = random.choice([
                "Что ты сделал за последний час?",
                "Ты движешься к целям?",
                "Ты не прокрастинируешь?",
            ])
            try:
                await bot.send_message(uid, f"🤖 {msg}")
            except:
                pass

@dp.message(lambda message: message.voice is not None)
async def voice_handler(message: types.Message):
    await message.answer("🎙 Голос получил, но пока отвечаю текстом")

@dp.message()
async def handle(message: types.Message):
    uid = str(message.from_user.id)
    text = message.text.lower()

    for k in data:
        if uid not in data[k]:
            data[k][uid] = []

    if not data["memory"][uid]:
        data["memory"][uid] = [SYSTEM]

    # профиль
    if text.startswith("я "):
        data["profile"][uid].append(text)
        save("profile", data["profile"])
        await message.answer("Запомнил")
        return

    # мысли
    if text.startswith("мысль"):
        thought = text.replace("мысль", "").strip()
        data["thoughts"][uid].append(thought)
        save("thoughts", data["thoughts"])
        await message.answer("Сохранил мысль")
        return

    # цели
    if text.startswith("цель"):
        data["goals"][uid].append(text.replace("цель", "").strip())
        save("goals", data["goals"])
        await message.answer("Цель добавлена")
        return

    # задачи
    if text.startswith("задача"):
        data["tasks"][uid].append({"text": text, "done": False})
        save("tasks", data["tasks"])
        await message.answer("Задача добавлена")
        return

    relevant = search_memory(uid, text)

    if "разбор" in text:
        prompt = f"""
Контекст:
{build_context(uid)}

Важные мысли:
{relevant}

Сделай анализ:
- где слабость
- что делать
- как расти
"""
    else:
        prompt = f"""
Контекст:
{build_context(uid)}

Важные мысли:
{relevant}

Сообщение:
{text}
"""

    data["memory"][uid].append({"role": "user", "content": prompt})

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": "openai/gpt-3.5-turbo", "messages": data["memory"][uid]}
    )

    reply = r.json()["choices"][0]["message"]["content"]

    data["memory"][uid].append({"role": "assistant", "content": reply})
    save("memory", data["memory"])

    await message.answer(reply)

async def main():
    asyncio.create_task(proactive_loop())
    await dp.start_polling(bot)

asyncio.run(main())
