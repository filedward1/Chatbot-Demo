from google import genai
from dotenv import load_dotenv

load_dotenv()

# Create client (automatically uses GEMINI_API_KEY environment variable)
client = genai.Client()

print("Chatbot is running. Type 'exit' to quit.\n")

while True:
    user_input = input("You: ")

    if user_input.lower() == "exit":
        break

    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=user_input,
    )
    print("Bot:", response.text)