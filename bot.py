import asyncio
from aiogram import Bot, Dispatcher, types
import os, requests, json, zipfile

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_KEY = os.getenv("OPENROUTER_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === DOWNLOAD MODEL ===
if not os.path.exists("model"):
    print("Downloading model...")
    url = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
    r = requests.get(url)

    with open("model.zip", "wb") as f:
        f.write(r.content)

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

# === SYSTEM ===
SYSTEM = {
    "role": "system",
    "content": """
Ты — умный ассистент уровня ChatGPT.

Правила:
- не тупи
- не переспрашивай
- понимай контекст
- говори естественно
- помогай думать
"""
}

# === SMART MEMORY ===
def get_relevant(uid, text):
    thoughts = data["thoughts"].get(uid, [])
    return [t for t in thoughts if any(w in t for w in text.split())][:3]

def get_context(uid):
    return f"""
Профиль: {data['profile'].get(uid, [])[:3]}
Цели: {data['goals'].get(uid, [])[:3]}
"""

# === VOICE ===
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
        data_chunk = wf.readframes(4000)
        if not data_chunk:
            break
        if rec.AcceptWaveform(data_chunk):
            text += js.loads(rec.Result()).get("text", "")

    text += js.loads(rec.FinalResult()).get("text", "")

    if not text:
        text = "не удалось распознать"

    await message.answer(f"🎙 {text}")

    fake = types.Message(
        message_id=message.message_id,
        date=message.date,
        chat=message.chat,
        from_user=message.from_user,
        text=text
    )

    await handle(fake)

# === MAIN ===
@dp.message()
async def handle(message: types.Message):
    uid = str(message.from_user.id)
    text = message.text

    for k in data:
        data[k].setdefault(uid, [])

    data.setdefault("memory", {}).setdefault(uid, [])

    # === SAVE FACTS ===
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

    relevant = get_relevant(uid, text)

    # === THINKING ===
    analysis = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [{
                "role": "user",
                "content": f"""
Контекст:
{get_context(uid)}

Мысли:
{relevant}

Сообщение:
{text}

Кратко:
1. Смысл
2. Что ответить
"""
            }]
        }
    )

    plan = analysis.json()["choices"][0]["message"]["content"]

    # === RESPONSE ===
    messages = [
        SYSTEM,
        {"role": "system", "content": f"Контекст:\n{get_context(uid)}"},
    ]

    messages += data["memory"][uid][-6:]

    messages.append({
        "role": "user",
        "content": f"""
Анализ:
{plan}

Ответь:
{text}
"""
    })

    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "openai/gpt-4o-mini",
            "messages": messages
        }
    )

    reply = res.json()["choices"][0]["message"]["content"]

    data["memory"][uid].append({"role": "user", "content": text})
    data["memory"][uid].append({"role": "assistant", "content": reply})
    data["memory"][uid] = data["memory"][uid][-10:]

    save("memory", data["memory"])

    await message.answer(reply)

# === RUN ===
async def main():
    await dp.start_polling(bot)

asyncio.run(main())
