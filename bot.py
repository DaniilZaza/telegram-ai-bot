import os, json, requests, asyncio
from aiogram import Bot, Dispatcher, types

# --- CONFIG ---
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- MEMORY FILES ---
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

SYSTEM = {"role": "system", "content": """
Ты — личный ассистент, коуч и система мышления.
Ты анализируешь пользователя, помогаешь достигать целей, выявляешь слабости, усиливаешь дисциплину.
Иногда давишь, если пользователь ленится. Не просто отвечай — веди.
"""}

def build_context(uid):
    return f"""
Профиль: {data['profile'].get(uid, [])}
Цели: {data['goals'].get(uid, [])}
Задачи: {data['tasks'].get(uid, [])}
Привычки: {data['habits'].get(uid, [])}
Мысли: {data['thoughts'].get(uid, [])}
"""

def search_memory(uid, text):
    memories = data["thoughts"].get(uid, [])
    relevant = [m for m in memories if any(w in m for w in text.split())]
    return relevant[:5]

def ask_ai(uid, prompt):
    data["memory"].setdefault(uid, [])
    messages = [SYSTEM] + data["memory"][uid][-6:] + [{"role": "user", "content": prompt}]
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": "openai/gpt-4o-mini", "messages": messages}
        )
        reply = r.json()["choices"][0]["message"]["content"]
    except:
        reply = "Ошибка AI (проверь API ключ или лимиты)"
    data["memory"][uid].append({"role": "user", "content": prompt})
    data["memory"][uid].append({"role": "assistant", "content": reply})
    save("memory", data["memory"])
    return reply

# --- HANDLER ---
@dp.message()
async def handle(message: types.Message):
    uid = str(message.from_user.id)
    text = message.text.lower()

    # создаём структуру, если нет
    for k in data:
        data.setdefault(k, {})
        data[k].setdefault(uid, [])

    # профиль
    if text.startswith("я "):
        data["profile"][uid].append(text)
        save("profile", data["profile"])
        await message.answer("Запомнил профиль ✅")
        return

    # мысль
    if text.startswith("мысль"):
        thought = text.replace("мысль","").strip()
        data["thoughts"][uid].append(thought)
        save("thoughts", data["thoughts"])
        await message.answer("Сохранил мысль 📝")
        return

    # цель
    if text.startswith("цель"):
        goal = text.replace("цель","").strip()
        data["goals"][uid].append(goal)
        save("goals", data["goals"])
        await message.answer("Цель добавлена 🎯")
        return

    # привычка
    if text.startswith("привычка"):
        habit = text.replace("привычка","").strip()
        data["habits"][uid].append(habit)
        save("habits", data["habits"])
        await message.answer("Привычка добавлена 💪")
        return

    # задача
    if text.startswith("задача"):
        task = text.replace("задача","").strip()
        data["tasks"][uid].append({"text": task, "done": False})
        save("tasks", data["tasks"])
        await message.answer("Задача добавлена ✅")
        return

    # разбор
    if "разбор" in text:
        relevant = search_memory(uid, text)
        prompt = f"""
Контекст:
{build_context(uid)}

Важные мысли:
{relevant}

Сообщение:
{text}

Сделай глубокий анализ:
- где слабость
- что делать
- как расти
"""
    else:
        prompt = f"""
Контекст:
{build_context(uid)}

Сообщение пользователя:
{text}
"""

    reply = ask_ai(uid, prompt)
    await message.answer(reply)

# --- RUN ---
async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
