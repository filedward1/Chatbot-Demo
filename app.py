from flask import Flask, render_template, request, jsonify
from chatbot_logic import get_bot_response

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    bot_reply = get_bot_response(user_message)
    return jsonify({"reply": bot_reply})

@app.route("/reset", methods=["POST"])
def reset():
    from chatbot_logic import reset_chat
    reset_chat()
    return jsonify({"status": "reset successful"})

if __name__ == "__main__":
    app.run(debug=True)