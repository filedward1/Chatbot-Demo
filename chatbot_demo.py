from google import genai
from dotenv import load_dotenv
from google.genai import types
import os
from supabase import create_client, Client

def fetch_rows(supabase: Client, table_name: str, columns: str = "*"):
    try:
        response = supabase.table(table_name).select(columns).execute()
        return response.data or []
    except Exception as e:
        print(f"Error fetching {table_name}: {e}")
        return []


def build_products_context(supabase: Client):
    laptops = fetch_rows(supabase, "laptop", "id,name,price,tags")
    printers = fetch_rows(supabase, "printer", "id,name,price,tags")

    lines = ["Laptops:"]
    if laptops:
        for item in laptops:
            lines.append(
                f"- {item.get('name', 'Unknown')} | price: {item.get('price', 'N/A')} | tags: {item.get('tags', '')}"
            )
    else:
        lines.append("- None available")

    lines.append("\nPrinters:")
    if printers:
        for item in printers:
            lines.append(
                f"- {item.get('name', 'Unknown')} | price: {item.get('price', 'N/A')} | tags: {item.get('tags', '')}"
            )
    else:
        lines.append("- None available")

    return "\n".join(lines)

load_dotenv()

if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
    print("Supabase credentials not found. Check your .env file.")
    exit()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

products_context = build_products_context(supabase)

# Create client (automatically uses GEMINI_API_KEY environment variable)
if not os.getenv("GEMINI_API_KEY"):
    print("API key not found. Check your .env file.")
    exit()
client = genai.Client()

system_prompt = f"""
You are a product recommendation and support chatbot.
Available products:
{products_context}

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