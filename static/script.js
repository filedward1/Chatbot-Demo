async function sendMessage() {
    const inputField = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");

    const userMessage = inputField.value;
    if (!userMessage) return;

    // Display user message
    chatBox.innerHTML += `<div class="user"><strong>You:</strong> ${userMessage}</div>`;

    inputField.value = "";

    const response = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: userMessage })
    });

    const data = await response.json();

    chatBox.innerHTML += `<div class="bot"><strong>Bot:</strong> ${data.reply}</div>`;

    chatBox.scrollTop = chatBox.scrollHeight;
}