import asyncio
from aiogram import Bot, Dispatcher, types
from flask import Flask, request, jsonify
import os, requests, json, zipfile

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# === DOWNLOAD MODEL ===
if not os.path.exists("model"):
    url = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
    r = requests.get(url)

    with open("model.zip", "wb") as f:
        f.write(r.content)

    import zipfile
    with zipfile.ZipFile("model.zip", 'r') as zip_ref:
        zip_ref.extractall()

    for name in os.listdir():
        if name.startswith("vosk-model"):
            os.rename(name, "model")

# === VOSK ===
from vosk import Model, KaldiRecognizer
import wave
import json as js
from pydub import AudioSegment

model = Model("model")

# === STORAGE ===
FILES = ["memory", "profile", "goals", "thoughts"]

def load(name):
    return json.load(open(f"{name}.json")) if os.path.exists(f"{name}.json") else {}

def save(name, data):
    json.dump(data, open(f"{name}.json", "w"))

data = {k: load(k) for k in FILES}

SYSTEM = {
    "role": "system",
    "content": "Ты умный ассистент как ChatGPT"
}

def get_context(uid):
    return f"""
Профиль: {data['profile'].get(uid, [])[:3]}
Цели: {data['goals'].get(uid, [])[:3]}
"""

def get_relevant(uid, text):
    thoughts = data["thoughts"].get(uid, [])
    return [t for t in thoughts if any(w in t for w in text.split())][:3]

# === AI FUNCTION (ОБЩАЯ) ===
def ask_ai(uid, text):
    data.setdefault("memory", {}).setdefault(uid, [])

    relevant = get_relevant(uid, text)

    messages = [
        SYSTEM,
        {"role": "system", "content": get_context(uid)}
    ]

    messages += data["memory"][uid][-6:]

    messages.append({"role": "user", "content": text})

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

# === TELEGRAM ===
@dp.message(lambda m: m.voice)
async def voice_handler(message: types.Message):
    file = await bot.get_file(message.voice.file_id)
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    r = requests.get(url)
    open("voice.ogg", "wb").write(r.content)

    sound = AudioSegment.from_ogg("voice.ogg")
    sound.export("voice.wav", format="wav")

    wf = wave.open("voice.wav", "rb")
    rec = KaldiRecognizer(model, wf.getframerate())

    text = ""
    while True:
        d = wf.readframes(4000)
        if not d:
            break
        if rec.AcceptWaveform(d):
            text += js.loads(rec.Result()).get("text", "")

    text += js.loads(rec.FinalResult()).get("text", "")

    await message.answer(f"🎙 {text}")
    reply = ask_ai(str(message.from_user.id), text)
    await message.answer(reply)

@dp.message()
async def handle(message: types.Message):
    uid = str(message.from_user.id)
    text = message.text

    reply = ask_ai(uid, text)
    await message.answer(reply)

# === WEB ===
@app.route("/")
def index():
    return open("index.html").read()

@app.route("/chat", methods=["POST"])
def chat():
    text = request.json["message"]
    uid = "web-user"

    reply = ask_ai(uid, text)

    return jsonify({"reply": reply})

# === RUN BOTH ===
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
