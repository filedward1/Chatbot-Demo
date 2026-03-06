# CHATBOT DEMO
This project is a practice implementation of a full-stack AI chatbot system.
It demonstrates how to design, develop, and integrate both frontend and backend
components to create a functional chatbot demo.

## Features
- Google Gemini AI for intelligent responses
- Product recommendations
- Troubleshooting assistance
- Conversation history storage with Supabase
- Multi-turn conversation support

## Setup Instructions

### 1. Environment Setup
Create a `.env` file in the project root with the following variables:
```
GEMINI_API_KEY=your_gemini_api_key_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Up Supabase Database
1. Run the setup script to see the required SQL:
   ```bash
   python setup_db.py
   ```

2. Connect to your Supabase project:
   - Go to https://supabase.com/dashboard
   - Select your project
   - Go to the SQL Editor

3. Create the required tables by running the SQL from the setup script:
   - Create `conversation` table (id UUID, created_at TIMESTAMP)
   - Create `messages` table (id UUID, conversation_id UUID, role TEXT, content TEXT, created_at TIMESTAMP)

### Database Schema

**conversation table:**
- `id` (UUID, Primary Key)
- `created_at` (TIMESTAMP)

**messages table:**
- `id` (UUID, Primary Key)
- `conversation_id` (UUID, Foreign Key to conversation.id)
- `role` (TEXT - 'user' or 'bot')
- `content` (TEXT)
- `created_at` (TIMESTAMP)

### 4. Run the Application
```bash
python app.py
```
The chatbot will be available at `http://localhost:5000`

## Project Structure
- `app.py` - Flask backend server
- `chatbot_logic.py` - Core chatbot logic with Gemini AI and Supabase integration
- `templates/index.html` - Main HTML frontend
- `static/style.css` - Styling
- `static/script.js` - Frontend interactivity
- `data/products.json` - Product database
- `data/troubleshooting.json` - Troubleshooting guides
- `requirements.txt` - Python dependencies
- `setup_db.py` - Database initialization script

## API Endpoints
- `GET /` - Serve the main chatbot interface
- `POST /chat` - Send a message to the chatbot
- `POST /reset` - Reset the current chat session
- `GET /history` - Get all conversation history
- `GET /history/<session_id>` - Get messages from a specific conversation