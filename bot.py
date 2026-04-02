import os, json, requests
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
API_KEY = os.getenv("OPENROUTER_API_KEY")

# Память чата
memory = {}
SYSTEM = {"role": "system", "content": "Ты умный ассистент"}

# Функция запроса к AI
def ask_ai(uid, text):
    memory.setdefault(uid, [])
    messages = [SYSTEM] + memory[uid][-6:] + [{"role": "user", "content": text}]
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": "openai/gpt-4o-mini", "messages": messages}
        )
        reply = r.json()["choices"][0]["message"]["content"]
    except:
        reply = "Ошибка AI (проверь API ключ или лимиты)"

    memory[uid].append({"role": "user", "content": text})
    memory[uid].append({"role": "assistant", "content": reply})
    return reply

# === WEB ===
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    text = request.json.get("message", "")
    reply = ask_ai("web", text)
    return jsonify({"reply": reply})

@app.route("/voice", methods=["POST"])
def voice():
    # Голос временно отключен
    return jsonify({"text": "", "reply": "Голос временно отключен"})

# === RUN ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
