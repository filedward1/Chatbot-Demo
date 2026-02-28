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