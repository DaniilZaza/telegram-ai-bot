import asyncio
from aiogram import Bot, Dispatcher, types
from flask import Flask, request, jsonify
import os, requests, json
import soundfile as sf
from vosk import Model, KaldiRecognizer

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

# === MODEL DOWNLOAD ===
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

# === STORAGE ===
FILES = ["memory"]
def load(name): return json.load(open(f"{name}.json")) if os.path.exists(f"{name}.json") else {}
def save(name,data): json.dump(data, open(f"{name}.json","w"))

data = {k: load(k) for k in FILES}

SYSTEM = {"role":"system","content":"Ты умный ассистент"}

# === AI ===
def ask_ai(uid,text):
    data.setdefault("memory",{}).setdefault(uid,[])
    messages=[SYSTEM]+data["memory"][uid][-6:]+[{"role":"user","content":text}]
    try:
        r=requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization":f"Bearer {API_KEY}"},
            json={"model":"openai/gpt-4o-mini","messages":messages}
        )
        reply=r.json()["choices"][0]["message"]["content"]
    except:
        reply="Ошибка API"
    data["memory"][uid].append({"role":"user","content":text})
    data["memory"][uid].append({"role":"assistant","content":reply})
    data["memory"][uid]=data["memory"][uid][-10:]
    save("memory",data["memory"])
    return reply

# === VOICE БЕЗ FFMPEG ===
@dp.message(lambda m: m.voice)
async def voice_handler(message: types.Message):
    uid=str(message.from_user.id)

    file=await bot.get_file(message.voice.file_id)
    url=f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    r=requests.get(url)
    open("voice.ogg","wb").write(r.content)

    # 🔥 ЧИТАЕМ OGG НАПРЯМУЮ
    data_audio, samplerate = sf.read("voice.ogg")

    rec = KaldiRecognizer(model, samplerate)

    text=""
    import numpy as np

    for i in range(0,len(data_audio),4000):
        chunk=data_audio[i:i+4000]
        chunk_bytes=(chunk*32767).astype("int16").tobytes()

        if rec.AcceptWaveform(chunk_bytes):
            text+=json.loads(rec.Result()).get("text","")

    text+=json.loads(rec.FinalResult()).get("text","")

    if not text:
        text="не удалось распознать"

    await message.answer(f"🎙 {text}")

    reply=ask_ai(uid,text)
    await message.answer(reply)

# === TEXT ===
@dp.message()
async def handle(message: types.Message):
    uid=str(message.from_user.id)
    reply=ask_ai(uid,message.text)
    await message.answer(reply)

# === WEB ===
@app.route("/")
def index():
    return """
    <html><body>
    <h2>AI</h2>
    <input id='i'><button onclick='s()'>Send</button>
    <div id='c'></div>
    <script>
    async function s(){
        let t=i.value
        c.innerHTML+="<p>"+t+"</p>"
        let r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:t})})
        let d=await r.json()
        c.innerHTML+="<p>"+d.reply+"</p>"
    }
    </script>
    </body></html>
    """

@app.route("/chat",methods=["POST"])
def chat():
    text=request.json["message"]
    return jsonify({"reply":ask_ai("web",text)})

# === RUN ===
async def run_bot():
    await dp.start_polling(bot)

def run_web():
    app.run(host="0.0.0.0",port=3000)

if __name__=="__main__":
    import threading
    threading.Thread(target=run_web).start()
    asyncio.run(run_bot())
from flask import request, jsonify

@app.route("/voice", methods=["POST"])
def voice():
    uid = "web-user"
    file = request.files.get("file")
    if not file:
        return jsonify({"text":"","reply":"Ошибка: нет файла"})
    file.save("voice.ogg")

    # Оффлайн распознавание через Vosk
    import soundfile as sf
    data_audio, samplerate = sf.read("voice.ogg", dtype="float32")

    from vosk import KaldiRecognizer
    import json, numpy as np
    rec = KaldiRecognizer(model, samplerate)
    text=""
    for i in range(0,len(data_audio),4000):
        chunk=data_audio[i:i+4000]
        chunk_bytes=(chunk*32767).astype("int16").tobytes()
        if rec.AcceptWaveform(chunk_bytes):
            text+=json.loads(rec.Result()).get("text","")
    text+=json.loads(rec.FinalResult()).get("text","")
    if not text: text="не удалось распознать"

    reply = ask_ai(uid, text)
    return jsonify({"text":text,"reply":reply})
