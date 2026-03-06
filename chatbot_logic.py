from google import genai
from dotenv import load_dotenv
from google.genai import types
import os
import json

import uuid
from datetime import datetime
from supabase import create_client, Client

# Current session ID
current_session_id = str(uuid.uuid4())

with open("data/products.json", "r") as f:
    products = json.load(f)

with open("data/troubleshooting.json") as f:
    troubleshooting_data = json.load(f)

load_dotenv()

# Initialize Supabase client
if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
    print("Supabase credentials not found. Check your .env file.")
    exit()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def reset_chat():
    global chat, current_session_id

    chat = client.chats.create(
        model="gemini-3-flash-preview",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
        )
    )

    current_session_id = str(uuid.uuid4())
    return current_session_id

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

# Create a chat session for multi-turn conversation
chat = client.chats.create(
    model='gemini-3-flash-preview',
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
    )
)

print("Chatbot is running. Type 'exit' to quit.\n")


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

def create_conversation_in_db():
    # """Create a new conversation record in the database"""
    try:
        response = supabase.table("conversation").insert({
            "id": current_session_id,
            "created_at": datetime.now().isoformat()
        }).execute()
        return response.data
    except Exception as e:
        # It may already exist (e.g. restoring an existing session)
        return None


def get_conversation_title(session_id: str):
    """Return the stored title for a conversation, if available."""
    try:
        response = supabase.table("conversation").select("title").eq("id", session_id).single().execute()
        if response.data and response.data.get("title"):
            return response.data.get("title")
    except Exception:
        pass

    return None


def set_conversation_title(session_id: str, title: str):
    """Store/update the conversation title in Supabase."""
    try:
        supabase.table("conversation").update({"title": title}).eq("id", session_id).execute()
        return True
    except Exception:
        # If this fails, we ignore it; the chat will still work without a title.
        return False


def maybe_generate_title_for_session(session_id: str):
    """Generate a short conversation title based on the first few messages."""
    # Don't regenerate if a title already exists.
    if get_conversation_title(session_id):
        return

    # Pull the first few messages for context.
    conv = get_conversation_messages(session_id)
    messages = conv.get("messages", [])
    if not messages:
        return

    # Use up to the first 4 messages (user+bot pairs) to create a title.
    sample = messages[:4]
    formatted = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in sample])

    prompt = f"""
    You are an assistant that generates a short, descriptive title for a conversation.
    Provide a concise title (2-6 words) that summarizes the topic of the conversation.

    Conversation:
    {formatted}

    Return only the title (no quotes or punctuation around it).
    """

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt
        )

        title = response.text.strip().strip('"').strip("'")
        if not title:
            return

        # Keep it reasonably short.
        if len(title) > 80:
            title = title[:80].rsplit(" ", 1)[0]

        set_conversation_title(session_id, title)
    except Exception:
        # Fail silently; conversation can still function normally.
        return


def set_current_session(session_id: str):
    """Set the current session id and ensure it exists in the DB."""
    global current_session_id
    current_session_id = session_id

    try:
        supabase.table("conversation").insert({
            "id": current_session_id,
            "created_at": datetime.now().isoformat()
        }).execute()
    except Exception:
        # Ignore if the conversation already exists.
        pass

def save_message_to_db(role, content):
    # """Save a message to the database"""
    # Ensure a conversation record exists before saving any messages.
    create_conversation_in_db()

    try:
        response = supabase.table("messages").insert({
            "id": str(uuid.uuid4()),
            "conversation_id": current_session_id,
            "role": role,
            "content": content,
            "created_at": datetime.now().isoformat()
        }).execute()

        return response.data
    except Exception as e:
        print(f"Error saving message: {e}")
        return None
    
def get_bot_response(user_message, session_id=None):
    global current_session_id

    # If the client is continuing an existing conversation, switch to that session.
    if session_id:
        set_current_session(session_id)

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

    # Save messages to Supabase
    save_message_to_db("user", user_message)
    save_message_to_db("bot", bot_reply)

    # Generate a short conversation title once we have at least one user + bot exchange.
    maybe_generate_title_for_session(current_session_id)

    return bot_reply

def get_conversation_history():
    # """Fetch all conversations from the database"""
    try:
        response = supabase.table("conversation").select("*").execute()
        conversations_dict = {}
        
        for conv in response.data:
            conv_id = conv["id"]
            title = conv.get("title") or get_conversation_title(conv_id)
            conversations_dict[conv_id] = {
                "created_at": conv["created_at"],
                "title": title,
                "messages": []
            }
        
        return conversations_dict
    except Exception as e:
        print(f"Error fetching conversation history: {e}")
        return {}

def get_conversation_messages(session_id):
    # """Fetch messages for a specific conversation"""
    try:
        response = supabase.table("messages").select("*").eq("conversation_id", session_id).order("created_at").execute()
        
        messages = []
        for msg in response.data:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"]
            })
        
        return {
            "id": session_id,
            "messages": messages
        }
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return {"id": session_id, "messages": []}


