import asyncio
from aiogram import Bot, Dispatcher, types
from flask import Flask, request, jsonify, render_template
import os, requests, json

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# === MEMORY ===
memory = {}

SYSTEM = {"role":"system","content":"Ты умный ассистент"}

def ask_ai(uid, text):
    memory.setdefault(uid, [])
    messages = [SYSTEM] + memory[uid][-6:] + [{"role":"user","content":text}]

    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization":f"Bearer {API_KEY}"},
            json={"model":"openai/gpt-4o-mini","messages":messages}
        )
        reply = r.json()["choices"][0]["message"]["content"]
    except:
        reply = "Ошибка AI (проверь API ключ или лимиты)"

    memory[uid].append({"role":"user","content":text})
    memory[uid].append({"role":"assistant","content":reply})

    return reply

# === TELEGRAM ===
@dp.message()
async def tg_handler(message: types.Message):
    uid = str(message.from_user.id)
    reply = ask_ai(uid, message.text)
    await message.answer(reply)

# === WEB ===
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    text = request.json["message"]
    reply = ask_ai("web", text)
    return jsonify({"reply": reply})

# === RUN ===
async def run_bot():
    await dp.start_polling(bot)

def run_web():
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    import threading
    threading.Thread(target=run_web).start()
    asyncio.run(run_bot())
