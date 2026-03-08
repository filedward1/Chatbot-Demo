from flask import Flask, render_template, request, jsonify
from chatbot_logic import (
    get_bot_response,
    reset_chat,
    get_conversation_history,
    get_conversation_messages,
    create_conversation_in_db,
    set_current_session,
    set_conversation_title,
    current_session_id,
)

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    session_id = request.json.get("session_id")

    bot_reply = get_bot_response(user_message, session_id=session_id)
    return jsonify({"reply": bot_reply, "session_id": current_session_id})

@app.route("/reset", methods=["POST"])
def reset():
    new_session_id = reset_chat()
    return jsonify({"status": "reset successful", "session_id": new_session_id})

@app.route("/set_session", methods=["POST"])
def set_session():
    session_id = request.json.get("session_id")
    if session_id:
        set_current_session(session_id)
        return jsonify({"status": "session set", "session_id": session_id})
    return jsonify({"status": "missing session_id"}), 400

@app.route("/history", methods=["GET"])
def get_history():
    conversations = get_conversation_history()
    return jsonify(conversations)

@app.route("/history/<session_id>", methods=["GET"])
def get_conversation(session_id):
    conversation = get_conversation_messages(session_id)
    return jsonify(conversation)

@app.route("/history/<session_id>/title", methods=["POST"])
def update_conversation_title(session_id):
    title = (request.json or {}).get("title", "")
    title = title.strip()

    if not title:
        return jsonify({"status": "missing title"}), 400

    ok = set_conversation_title(session_id, title)
    if not ok:
        return jsonify({"status": "failed to update title"}), 500

    return jsonify({"status": "ok", "id": session_id, "title": title})

if __name__ == "__main__":
    app.run(debug=True)