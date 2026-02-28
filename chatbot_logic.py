from google import genai
from dotenv import load_dotenv
from google.genai import types
import os
import json

import uuid
from datetime import datetime

# Store conversations
conversations = {}

# Current session ID
current_session_id = str(uuid.uuid4())

with open("data/products.json", "r") as f:
    products = json.load(f)

with open("data/troubleshooting.json") as f:
    troubleshooting_data = json.load(f)

load_dotenv()

def reset_chat():
    global chat, current_session_id

    chat = client.chats.create(
        model="gemini-3-flash-preview",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
        )
    )

    current_session_id = str(uuid.uuid4())

# Create client (automatically uses GEMINI_API_KEY environment variable)
if not os.getenv("GEMINI_API_KEY"):
    print("API key not found. Check your .env file.")
    exit()
client = genai.Client()

system_prompt = """
You are a product recommendation and support chatbot.
Available products:
{products}

Instructions:
1. Identify what the user needs.
2. Recommend only from available products.
3. If troubleshooting, give step-by-step solution.
4. Keep answer clear.
"""

print("Chatbot is running. Type 'exit' to quit.\n")

# Create a chat session for multi-turn conversation
chat = client.chats.create(
    model='gemini-3-flash-preview',
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
    )
)

def handle_troubleshooting(user_message):
    for item in troubleshooting_data:
        if item["issue"] in user_message.lower():
            steps = "\n".join([f"{i+1}. {step}" for i, step in enumerate(item["steps"])])
            return f"Here are the troubleshooting steps:\n{steps}"

    return "Please describe the issue in more detail."

def extract_intent(user_message):
    intent_prompt = f"""
    Analyze this message:

    "{user_message}"

    Extract:
    - intent (recommendation, troubleshooting, aftersales)
    - product_type (laptop, printer, unknown)
    - features (list)

    Return JSON only.
    """

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=intent_prompt
    )

    try:
        return json.loads(response.text)
    except:
        return None
    
def get_bot_response(user_message):
    global current_session_id

    intent_data = extract_intent(user_message)

    if intent_data and intent_data.get("intent") == "troubleshooting":
        bot_reply = handle_troubleshooting(user_message)
    else:
        prompt = f"""
        User intent:
        {intent_data}

        Available products:
        {products}

        Provide a structured response.
        """
        response = chat.send_message(prompt)
        bot_reply = response.text

    # Save conversation
    if current_session_id not in conversations:
        conversations[current_session_id] = {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": []
        }

    conversations[current_session_id]["messages"].append({
        "user": user_message,
        "bot": bot_reply
    })

    return bot_reply