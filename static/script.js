let currentSessionId = null;

async function sendMessage() {
    const inputField = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const button = document.querySelector("button");

    const userMessage = inputField.value.trim();
    if (!userMessage) return;

    // Display user message
    chatBox.innerHTML += `
        <div class="user">
            <strong>You:</strong> ${userMessage}
        </div>
    `;

    inputField.value = "";
    inputField.disabled = true;
    button.disabled = true;

    // Add typing indicator
    const typingDiv = document.createElement("div");
    typingDiv.className = "bot typing";
    typingDiv.id = "typing-indicator";
    typingDiv.innerHTML = "<strong>Bot:</strong> typing...";
    chatBox.appendChild(typingDiv);

    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: userMessage, session_id: currentSessionId })
        });

        const data = await response.json();

        // Keep session tracking in sync (if server returns it)
        if (data.session_id) {
            currentSessionId = data.session_id;
        }

        // Remove typing indicator
        typingDiv.remove();

        // Show bot reply
        chatBox.innerHTML += `
            <div class="bot">
                <strong>Bot:</strong> ${data.reply}
            </div>
        `;

        // Refresh history to show updated title (generated after first few messages)
        loadHistory();

    } catch (error) {
        typingDiv.remove();
        chatBox.innerHTML += `
            <div class="bot">
                <strong>Bot:</strong> Error connecting to server.
            </div>
        `;
    }

    inputField.disabled = false;
    button.disabled = false;
    inputField.focus();
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function resetChat() {
    const response = await fetch("/reset", {
        method: "POST"
    });

    const data = await response.json();
    currentSessionId = data.session_id || null;

    document.getElementById("chat-box").innerHTML = "";
}

async function loadHistory() {
    const response = await fetch("/history");
    const data = await response.json();

    const historyList = document.getElementById("history-list");
    historyList.innerHTML = "";

    for (let sessionId in data) {
        const li = document.createElement("li");
        const title = data[sessionId].title;
        const created = new Date(data[sessionId].created_at).toLocaleString();
        li.innerText = title ? `${title} (${created})` : created;
        li.onclick = () => loadConversation(sessionId);
        historyList.appendChild(li);
    }
}

async function loadConversation(sessionId) {
    currentSessionId = sessionId;

    const response = await fetch(`/history/${sessionId}`);
    const data = await response.json();

    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";

    // Handle both old format (user/bot pairs) and new format (role-based)
    if (data.messages && data.messages.length > 0) {
        if (data.messages[0].role) {
            // New format with role field
            data.messages.forEach(msg => {
                if (msg.role === "user") {
                    chatBox.innerHTML += `<div class="user"><strong>You:</strong> ${msg.content}</div>`;
                } else if (msg.role === "bot") {
                    chatBox.innerHTML += `<div class="bot"><strong>Bot:</strong> ${msg.content}</div>`;
                }
            });
        } else if (data.messages[0].user) {
            // Old format with user/bot fields
            data.messages.forEach(msg => {
                chatBox.innerHTML += `
                    <div class="user"><strong>You:</strong> ${msg.user}</div>
                    <div class="bot"><strong>Bot:</strong> ${msg.bot}</div>
                `;
            });
        }
    }
}

window.onload = loadHistory;