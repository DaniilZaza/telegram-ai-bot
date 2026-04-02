from flask import Flask, request, jsonify
import requests, os

app = Flask(__name__)

API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json["message"]

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": user_message}]
        }
    )

    reply = response.json()["choices"][0]["message"]["content"]

    return jsonify({"reply": reply})

app.run(host="0.0.0.0", port=3000)
