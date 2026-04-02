import asyncio
from aiogram import Bot, Dispatcher, types
from flask import Flask, request, jsonify
import os, requests, json, wave
from vosk import Model, KaldiRecognizer

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# === VOSK MODEL ===
if not os.path.exists("model"):
    import zipfile
    import requests
    print("Downloading Vosk model...")
    url = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
    r = requests.get(url)
    with open("model.zip", "wb") as f:
        f.write(r.content)
    with zipfile.ZipFile("model.zip", "r") as zip_ref:
        zip_ref.extractall()
    for name in os.listdir():
        if name.startswith("vosk-model"):
            os.rename(name, "model")
print("Vosk model ready")
model = Model("model")

# === STORAGE ===
FILES = ["memory", "profile", "goals", "thoughts"]
def load(name): return json.load(open(f"{name}.json")) if os.path.exists(f"{name}.json") else {}
def save(name, data): json.dump(data, open(f"{name}.json", "w"))
data = {k: load(k) for k in FILES}

SYSTEM = {"role": "system", "content": "Ты умный ассистент, отвечай понятно, без лишнего"}

def get_context(uid):
    return f"Профиль: {data['profile'].get(uid, [])[:3]}\nЦели: {data['goals'].get(uid, [])[:3]}"

def ask_ai(uid, text):
    data.setdefault("memory", {}).setdefault(uid, [])
    messages = [SYSTEM] + data["memory"][uid][-6:] + [{"role":"user","content":text}]
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model":"openai/gpt-4o-mini","messages":messages}
        )
        reply = r.json()["choices"][0]["message"]["content"]
    except:
        reply = "Ошибка API или превышен лимит"
    data["memory"][uid].append({"role":"user","content":text})
    data["memory"][uid].append({"role":"assistant","content":reply})
    data["memory"][uid] = data["memory"][uid][-10:]
    save("memory", data["memory"])
    return reply

# === VOICE HANDLER ===
@dp.message(lambda m: m.voice)
async def voice_handler(message: types.Message):
    file = await bot.get_file(message.voice.file_id)
    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    r = requests.get(url)
    with open("voice.ogg", "wb") as f:
        f.write(r.content)
    # конвертируем ogg в wav с помощью vosk-recognizer
    import subprocess
    subprocess.run(f"ffmpeg -i voice.ogg -ar 16000 -ac 1 voice.wav", shell=True)
    wf = wave.open("voice.wav", "rb")
    rec = KaldiRecognizer(model, wf.getframerate())
    text = ""
    while True:
        data_chunk = wf.readframes(4000)
        if len(data_chunk) == 0: break
        if rec.AcceptWaveform(data_chunk):
            text += json.loads(rec.Result()).get("text","")
    text += json.loads(rec.FinalResult()).get("text","")
    if not text: text = "не удалось распознать"
    await message.answer(f"🎙 {text}")
    reply = ask_ai(str(message.from_user.id), text)
    await message.answer(reply)

# === TEXT HANDLER ===
@dp.message()
async def handle(message: types.Message):
    uid = str(message.from_user.id)
    text = message.text
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
    return open("index.html").read()

@app.route("/chat", methods=["POST"])
def chat():
    text = request.json["message"]
    reply = ask_ai("web-user", text)
    return jsonify({"reply": reply})

# === RUN BOTH ===
async def run_bot(): await dp.start_polling(bot)
def run_web(): app.run(host="0.0.0.0", port=3000)
if __name__ == "__main__":
    import threading
    threading.Thread(target=run_web).start()
    asyncio.run(run_bot())
