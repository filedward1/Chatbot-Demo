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
            body: JSON.stringify({ message: userMessage })
        });

        const data = await response.json();

        // Remove typing indicator
        typingDiv.remove();

        // Show bot reply
        chatBox.innerHTML += `
            <div class="bot">
                <strong>Bot:</strong> ${data.reply}
            </div>
        `;

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
    await fetch("/reset", {
        method: "POST"
    });

    document.getElementById("chat-box").innerHTML = "";
}

async function loadHistory() {
    const response = await fetch("/history");
    const data = await response.json();

    const historyList = document.getElementById("history-list");
    historyList.innerHTML = "";

    for (let sessionId in data) {
        const li = document.createElement("li");
        li.innerText = data[sessionId].created_at;
        li.onclick = () => loadConversation(sessionId);
        historyList.appendChild(li);
    }
}

async function loadConversation(sessionId) {
    const response = await fetch(`/history/${sessionId}`);
    const data = await response.json();

    const chatBox = document.getElementById("chat-box");
    chatBox.innerHTML = "";

    data.messages.forEach(msg => {
        chatBox.innerHTML += `
            <div class="user"><strong>You:</strong> ${msg.user}</div>
            <div class="bot"><strong>Bot:</strong> ${msg.bot}</div>
        `;
    });
}

window.onload = loadHistory;