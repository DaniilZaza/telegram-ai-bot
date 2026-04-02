import asyncio
from aiogram import Bot, Dispatcher, types
from flask import Flask, request, jsonify
import os, requests, json

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# === STORAGE ===
FILES = ["memory", "profile", "goals"]

def load(name):
    return json.load(open(f"{name}.json")) if os.path.exists(f"{name}.json") else {}

def save(name, data):
    json.dump(data, open(f"{name}.json", "w"))

data = {k: load(k) for k in FILES}

SYSTEM = {
    "role": "system",
    "content": "Ты умный ассистент как ChatGPT. Отвечай понятно, без лишнего."
}

# === AI ===
def ask_ai(uid, text):
    data.setdefault("memory", {}).setdefault(uid, [])

    messages = [SYSTEM] + data["memory"][uid][-6:] + [
        {"role": "user", "content": text}
    ]

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "openai/gpt-4o-mini",
            "messages": messages
        }
    )

    reply = r.json()["choices"][0]["message"]["content"]

    data["memory"][uid].append({"role": "user", "content": text})
    data["memory"][uid].append({"role": "assistant", "content": reply})
    data["memory"][uid] = data["memory"][uid][-10:]

    save("memory", data["memory"])

    return reply

# === VOICE (СТАБИЛЬНО через API) ===
def transcribe_voice(file_bytes):
    r = requests.post(
        "https://openrouter.ai/api/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        files={"file": ("voice.ogg", file_bytes)},
        data={"model": "openai/whisper-1"}
    )

    return r.json().get("text", "")

# === TELEGRAM ===
@dp.message(lambda m: m.voice)
async def voice_handler(message: types.Message):
    file = await bot.get_file(message.voice.file_id)
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    r = requests.get(url)

    text = transcribe_voice(r.content)

    if not text:
        text = "не удалось распознать"

    await message.answer(f"🎙 {text}")

    reply = ask_ai(str(message.from_user.id), text)
    await message.answer(reply)

@dp.message()
async def handle(message: types.Message):
    uid = str(message.from_user.id)
    text = message.text

    # сохранение фактов
    if text.lower().startswith("я "):
        data.setdefault("profile", {}).setdefault(uid, []).append(text)
        save("profile", data["profile"])
        await message.answer("Запомнил")
        return

    if text.lower().startswith("цель"):
        data.setdefault("goals", {}).setdefault(uid, []).append(text)
        save("goals", data["goals"])
        await message.answer("Цель добавлена")
        return

    reply = ask_ai(uid, text)
    await message.answer(reply)

# === WEB ===
@app.route("/")
def index():
    return """
    <html>
    <body>
    <h2>AI Assistant</h2>
    <div id='chat'></div>
    <input id='input'/>
    <button onclick='send()'>Send</button>

    <script>
    async function send(){
        let input = document.getElementById("input")
        let text = input.value

        document.getElementById("chat").innerHTML += "<p>Ты: "+text+"</p>"

        let res = await fetch("/chat", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: text})
        })

        let data = await res.json()

        document.getElementById("chat").innerHTML += "<p>Бот: "+data.reply+"</p>"
        input.value = ""
    }
    </script>
    </body>
    </html>
    """

@app.route("/chat", methods=["POST"])
def chat():
    text = request.json["message"]
    reply = ask_ai("web-user", text)
    return jsonify({"reply": reply})

# === RUN ===
async def run_bot():
    await dp.start_polling(bot)

def run_web():
    app.run(host="0.0.0.0", port=3000)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(run_bot())

    import threading
    threading.Thread(target=run_web).start()

    loop.run_forever()
