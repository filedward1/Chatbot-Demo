let currentSessionId = null;
let conversationStarted = false;
let sidebarPinnedOpen = false;

function enterChatMode() {
    if (conversationStarted) return;
    conversationStarted = true;

    const container = document.querySelector('.chat-container');
    container.classList.remove('centered');

    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = 'none';
}

async function sendMessage() {
    enterChatMode();

    const inputField = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const button = document.getElementById("send-btn");

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

        // Show bot reply (render markdown if present)
        const formattedReply = marked.parse(data.reply);
        chatBox.innerHTML += `
            <div class="bot">
                <strong>Bot:</strong>
                ${formattedReply}
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

    conversationStarted = false;
    const container = document.querySelector('.chat-container');
    container.classList.add('centered');

    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = '';

    document.getElementById("chat-box").innerHTML = "";
}

function setSidebarCollapsed(collapsed) {
    const sidebar = document.querySelector('.history-panel');
    const menuBtnImgs = document.querySelectorAll('.sidebar-menu img');
    if (!sidebar || !menuBtnImgs.length) return;

    sidebar.classList.toggle('collapsed', collapsed);

    // Use different menu icon depending on collapsed state
    menuBtnImgs.forEach(img => {
        img.src = collapsed ? '/static/image/book.svg' : '/static/image/book-open-text.svg';
    });
}

function toggleSidebar() {
    const sidebar = document.querySelector('.history-panel');
    if (!sidebar) return;

    const isCollapsed = sidebar.classList.contains('collapsed');
    if (isCollapsed) {
        // Expand and pin open when clicked
        sidebarPinnedOpen = true;
        setSidebarCollapsed(false);
    } else {
        // Collapse and unpin when clicked again
        sidebarPinnedOpen = false;
        setSidebarCollapsed(true);
    }
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
    enterChatMode();
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
                const formatted = marked.parse(msg.content);
                if (msg.role === "user") {
                    chatBox.innerHTML += `<div class="user"><strong>You:</strong> ${formatted}</div>`;
                } else if (msg.role === "bot") {
                    chatBox.innerHTML += `<div class="bot"><strong>Bot:</strong> ${formatted}</div>`;
                }
            });
        } else if (data.messages[0].user) {
            // Old format with user/bot fields
            data.messages.forEach(msg => {
                const userFormatted = marked.parse(msg.user);
                const botFormatted = marked.parse(msg.bot);
                chatBox.innerHTML += `
                    <div class="user"><strong>You:</strong> ${userFormatted}</div>
                    <div class="bot"><strong>Bot:</strong> ${botFormatted}</div>
                `;
            });
        }
    }
}

window.onload = () => {
    const inputField = document.getElementById('user-input');
    inputField.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            sendMessage();
        }
    });

    const newChatBtn = document.getElementById('new-chat-btn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', resetChat);
    }

    const menuBtns = document.querySelectorAll('.sidebar-menu');
    menuBtns.forEach((menuBtn) => {
        menuBtn.addEventListener('click', toggleSidebar);
    });

    const collapsedSearch = document.querySelector('.collapsed-search');
    if (collapsedSearch) {
        collapsedSearch.addEventListener('click', () => {
            setSidebarCollapsed(false);
            sidebarPinnedOpen = true;
        });
    }

    const collapsedNew = document.querySelector('.collapsed-new');
    if (collapsedNew) {
        collapsedNew.addEventListener('click', () => {
            setSidebarCollapsed(false);
            sidebarPinnedOpen = true;
            resetChat();
        });
    }

    // No auto collapse on mouse leave: sidebar stays in chosen state.

    loadHistory();
};