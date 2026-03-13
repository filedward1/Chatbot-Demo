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
last_fetch_status = {}

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
You are LEXA, which stands for Laptop EXpert Assistant.

Identity and tone:
- LEXA is modern, confident, and tech-savvy.
- LEXA specializes in expert laptop guidance and personalized support.
- Keep responses helpful, concise, and friendly.
- Speak in first person as LEXA when appropriate.

Name explanation for internal behavior alignment:
LEXA stands for Laptop EXpert Assistant. The name emphasizes expertise specifically in laptops - "LEX" directly highlighting "Laptop EXpert." LEXA represents smart, expert guidance that makes laptop shopping effortless.

Scope:
- Primary focus: laptop recommendations, specs, comparisons, and buying guidance.
- Secondary support: troubleshooting and aftersales support.

Instructions:
1. Identify what the user needs.
2. Recommend only from available products provided in the current prompt context.
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


def _fetch_rows(table_name: str, columns: str = "*"):
    """Fetch rows from a Supabase table and return a list."""
    global last_fetch_status
    try:
        response = supabase.table(table_name).select(columns).execute()
        rows = response.data or []
        last_fetch_status[table_name] = {
            "ok": True,
            "count": len(rows),
            "error": None,
            "checked_at": datetime.now().isoformat(),
        }
        return rows
    except Exception as e:
        print(f"Error fetching {table_name}: {e}")
        last_fetch_status[table_name] = {
            "ok": False,
            "count": 0,
            "error": str(e),
            "checked_at": datetime.now().isoformat(),
        }
        return []


def fetch_product_catalog():
    """Fetch product catalog data from Supabase laptop and printer tables."""
    laptops = _fetch_rows("laptop", "id,name,price,tags")
    printers = _fetch_rows("printer", "id,name,price,tags")
    return {
        "laptop": laptops,
        "printer": printers,
    }


def format_product_catalog(catalog: dict):
    """Create a compact readable product catalog text block for prompts."""
    laptop_rows = catalog.get("laptop", [])
    printer_rows = catalog.get("printer", [])

    lines = ["Laptops:"]
    if laptop_rows:
        for item in laptop_rows:
            lines.append(
                f"- {item.get('name', 'Unknown')} | price: {item.get('price', 'N/A')} | tags: {item.get('tags', '')}"
            )
    else:
        lines.append("- None available")

    lines.append("\nPrinters:")
    if printer_rows:
        for item in printer_rows:
            lines.append(
                f"- {item.get('name', 'Unknown')} | price: {item.get('price', 'N/A')} | tags: {item.get('tags', '')}"
            )
    else:
        lines.append("- None available")

    return "\n".join(lines)


def _parse_troubleshooting_steps(raw_steps):
    """Normalize troubleshooting steps from text/JSON into a list of step strings."""
    if isinstance(raw_steps, list):
        return [str(step).strip() for step in raw_steps if str(step).strip()]

    if raw_steps is None:
        return []

    if isinstance(raw_steps, str):
        text = raw_steps.strip()
        if not text:
            return []

        # Accept JSON array text if the DB stores steps as serialized JSON.
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(step).strip() for step in parsed if str(step).strip()]
            except Exception:
                pass

        if "\n" in text:
            return [part.strip(" -\t") for part in text.splitlines() if part.strip()]

        if ";" in text:
            return [part.strip(" -\t") for part in text.split(";") if part.strip()]

        return [text]

    return [str(raw_steps).strip()]


def fetch_troubleshooting_entries():
    """Fetch troubleshooting rows from Supabase troubleshooting table."""
    rows = _fetch_rows("troubleshooting", "device,issue,steps")
    normalized = []
    for row in rows:
        normalized.append({
            "device": (row.get("device") or "").strip(),
            "issue": (row.get("issue") or "").strip(),
            "steps": _parse_troubleshooting_steps(row.get("steps")),
        })
    return normalized


def get_catalog_diagnostics():
    """Return a quick health snapshot for Supabase-backed catalog tables."""
    catalog = fetch_product_catalog()
    troubleshooting_rows = fetch_troubleshooting_entries()

    laptop_rows = catalog.get("laptop", [])
    printer_rows = catalog.get("printer", [])

    return {
        "catalog_counts": {
            "laptop": len(laptop_rows),
            "printer": len(printer_rows),
            "troubleshooting": len(troubleshooting_rows),
        },
        "sample_rows": {
            "laptop": [
                {
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "tags": item.get("tags"),
                }
                for item in laptop_rows[:3]
            ],
            "printer": [
                {
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "tags": item.get("tags"),
                }
                for item in printer_rows[:3]
            ],
            "troubleshooting": [
                {
                    "device": item.get("device"),
                    "issue": item.get("issue"),
                    "steps_count": len(item.get("steps", [])),
                }
                for item in troubleshooting_rows[:3]
            ],
        },
        "fetch_status": last_fetch_status,
    }


def handle_troubleshooting(user_message):
    user_message_lower = user_message.lower()
    troubleshooting_data = fetch_troubleshooting_entries()

    for item in troubleshooting_data:
        issue = (item.get("issue") or "").lower()
        device = (item.get("device") or "").lower()
        if issue and issue in user_message_lower:
            steps_list = item.get("steps", [])
            steps = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps_list)])
            if not steps:
                return "LEXA here. I found that issue, but no step-by-step fix is saved yet."

            if device:
                return f"LEXA here. For your {device}, try these troubleshooting steps:\n{steps}"

            return f"LEXA here. Try these troubleshooting steps:\n{steps}"

    return "LEXA here. Please describe the issue in more detail so I can guide you better."

def extract_intent(user_message, conversation_history=None):
    context_block = ""
    if conversation_history:
        formatted = "\n".join(
            [f"{m['role'].capitalize()}: {m['content']}" for m in conversation_history[-6:]]
        )
        context_block = f"Recent conversation:\n{formatted}\n\n"

    intent_prompt = f"""
    {context_block}Analyze this message:

    "{user_message}"

    Extract:
    - intent (recommendation, troubleshooting, aftersales, product_detail, or general)
    - product_type (laptop, printer, or the specific product name/type being referred to based on the conversation; use "unknown" only if truly unclear)
    - features (list)
    - context_product (if this is a follow-up about a previously discussed product, name it here; otherwise null)

    Use the recent conversation to resolve vague references (e.g. "its price", "give me the specs", "what about the warranty").
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
    existing_title = get_conversation_title(session_id)
    if existing_title:
        return existing_title

    # Pull the first few messages for context.
    conv = get_conversation_messages(session_id)
    messages = conv.get("messages", [])
    if not messages:
        return None

    # Build a deterministic fallback title from the first user message.
    first_user_message = ""
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content"):
            first_user_message = msg.get("content", "").strip()
            break

    fallback_title = "New Conversation"
    if first_user_message:
        fallback_title = " ".join(first_user_message.split())
        if len(fallback_title) > 80:
            fallback_title = fallback_title[:80].rsplit(" ", 1)[0]
        if not fallback_title:
            fallback_title = "New Conversation"

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
            title = fallback_title

        # Keep it reasonably short.
        if len(title) > 80:
            title = title[:80].rsplit(" ", 1)[0]

        if not title:
            title = fallback_title

        set_conversation_title(session_id, title)
        return title
    except Exception:
        # If LLM title generation fails, still set a deterministic fallback title.
        set_conversation_title(session_id, fallback_title)
        return fallback_title


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

    # Fetch recent messages so vague follow-ups can be resolved with context.
    conv = get_conversation_messages(current_session_id)
    recent_messages = conv.get("messages", [])[-6:]

    intent_data = extract_intent(user_message, conversation_history=recent_messages)

    if intent_data and intent_data.get("intent") == "troubleshooting":
        bot_reply = handle_troubleshooting(user_message)
    else:
        catalog = fetch_product_catalog()
        products_context = format_product_catalog(catalog)

        # Build a conversation context block so the LLM can resolve follow-up references.
        context_block = ""
        if recent_messages:
            formatted_history = "\n".join(
                [f"{m['role'].capitalize()}: {m['content']}" for m in recent_messages]
            )
            context_block = f"Recent conversation:\n{formatted_history}\n\n"

        prompt = f"""
        {context_block}User message: {user_message}

        User intent:
        {intent_data}

        Available products:
        {products_context}

        Instructions:
        - Respond as LEXA (Laptop EXpert Assistant) with a modern, confident, tech-savvy tone.
        - Keep recommendations focused on laptops and practical buying guidance whenever relevant.
        - If this is a follow-up question referring to a previously recommended product (e.g. "give me the price", "what are the specs", "show me the warranty"), identify that product from the conversation context and answer specifically about it.
        - Do not ask for clarification if the referenced product is clear from the conversation history.
        - Provide a structured, clear response.
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


def delete_conversation(session_id: str):
    """Delete a conversation and all of its messages."""
    try:
        supabase.table("messages").delete().eq("conversation_id", session_id).execute()
        supabase.table("conversation").delete().eq("id", session_id).execute()
        return True
    except Exception as e:
        print(f"Error deleting conversation: {e}")
        return False


