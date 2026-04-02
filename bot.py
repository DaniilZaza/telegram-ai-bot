import asyncio
from aiogram import Bot, Dispatcher, types
from flask import Flask, request, jsonify, render_template
import os, requests, json
import soundfile as sf
from vosk import Model, KaldiRecognizer
import numpy as np

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# === MODEL ===
if not os.path.exists("model"):
    import zipfile
    print("Downloading Vosk...")
    url = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
    r = requests.get(url)
    open("model.zip","wb").write(r.content)
    zipfile.ZipFile("model.zip").extractall()
    for f in os.listdir():
        if f.startswith("vosk-model"):
            os.rename(f,"model")

model = Model("model")

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
        reply = "Ошибка AI (лимит или API)"

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

@app.route("/voice", methods=["POST"])
def voice():
    file = request.files.get("file")
    if not file:
        return jsonify({"text":"","reply":"нет файла"})

    file.save("voice.ogg")

    # распознавание
    data_audio, samplerate = sf.read("voice.ogg", dtype="float32")
    rec = KaldiRecognizer(model, samplerate)

    text = ""
    for i in range(0, len(data_audio), 4000):
        chunk = data_audio[i:i+4000]
        chunk_bytes = (chunk * 32767).astype("int16").tobytes()

        if rec.AcceptWaveform(chunk_bytes):
            text += json.loads(rec.Result()).get("text","")

    text += json.loads(rec.FinalResult()).get("text","")

    if not text:
        text = "не удалось распознать"

    reply = ask_ai("web", text)

    return jsonify({"text": text, "reply": reply})

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
