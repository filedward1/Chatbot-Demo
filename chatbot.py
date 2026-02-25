from google import genai
from dotenv import load_dotenv
from google.genai import types
import os
import json

with open("data/products.json", "r") as f:
    products = json.load(f)

load_dotenv()

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

while True:
    user_input = input("You: ")

    if user_input.lower() == "exit":
        break

    response = chat.send_message(user_input)
    print("Bot:", response.text)
    print()