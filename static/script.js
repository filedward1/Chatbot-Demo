let currentSessionId = null;
let conversationStarted = false;
let sidebarPinnedOpen = false;
let historyCache = [];

function enterChatMode() {
    if (conversationStarted) return;
    conversationStarted = true;

    const container = document.querySelector('.chat-container');
    container.classList.remove('centered');

    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = 'none';
}

function appendMessage(role, content, options = {}) {
    const { isHtml = false, typing = false, id = null } = options;
    const chatBox = document.getElementById("chat-box");
    if (!chatBox) return null;

    const row = document.createElement("div");
    row.className = `message-row ${role === "user" ? "message-user" : "message-bot"}`;
    if (typing) row.classList.add("typing");
    if (id) row.id = id;

    const avatar = document.createElement("img");
    avatar.className = "message-avatar";
    avatar.src = role === "user" ? "/static/image/user.svg" : "/static/image/logo-img.png";
    avatar.alt = role === "user" ? "User" : "Bot";

    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role === "user" ? "user-bubble" : "bot-bubble"}`;

    if (isHtml) {
        bubble.innerHTML = content;
    } else {
        bubble.textContent = content;
    }

    if (role === "user") {
        row.appendChild(bubble);
        row.appendChild(avatar);
    } else {
        row.appendChild(avatar);
        row.appendChild(bubble);
    }

    chatBox.appendChild(row);
    return row;
}

async function sendMessage() {
    enterChatMode();

    const inputField = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const button = document.getElementById("send-btn");

    const userMessage = inputField.value.trim();
    if (!userMessage) return;

    // Display user message as a right-aligned chat bubble.
    appendMessage("user", userMessage);

    inputField.value = "";
    inputField.disabled = true;
    button.disabled = true;

    // Add typing indicator
    const typingDiv = appendMessage("bot", "typing...", { typing: true, id: "typing-indicator" });

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
        appendMessage("bot", formattedReply, { isHtml: true });

        // Refresh history to show updated title (generated after first few messages)
        loadHistory();

    } catch (error) {
        typingDiv.remove();
        appendMessage("bot", "Error connecting to server.");
    }

    inputField.disabled = false;
    button.disabled = false;
    inputField.focus();
    chatBox.scrollTop = chatBox.scrollHeight;
}

function applyNewChatUIState() {
    conversationStarted = false;

    const container = document.querySelector('.chat-container');
    container.classList.add('centered');

    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = '';

    const chatBox = document.getElementById("chat-box");
    if (chatBox) chatBox.innerHTML = "";

    const inputField = document.getElementById("user-input");
    if (inputField) {
        inputField.value = "";
        inputField.disabled = false;
    }

    const sendButton = document.getElementById("send-btn");
    if (sendButton) sendButton.disabled = false;

    const typing = document.getElementById("typing-indicator");
    if (typing) typing.remove();

    closeSearchModal();
}

async function createNewChat() {
    applyNewChatUIState();

    try {
        const response = await fetch("/reset", {
            method: "POST"
        });

        const data = await response.json();
        currentSessionId = data.session_id || null;
    } catch (error) {
        // Keep the UI usable even if reset API is temporarily unavailable.
        currentSessionId = null;
    }

    await loadHistory();

    const inputField = document.getElementById("user-input");
    if (inputField) inputField.focus();
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

function openSearchModal() {
    const modal = document.getElementById('search-modal');
    const queryInput = document.getElementById('search-query');
    if (!modal || !queryInput) return;

    // Refresh history cache before searching
    loadHistory().then(() => {
        modal.classList.add('open');
        queryInput.value = '';
        renderSearchResults('');
        setTimeout(() => queryInput.focus(), 0);
    });
}

function closeSearchModal() {
    const modal = document.getElementById('search-modal');
    if (!modal) return;
    modal.classList.remove('open');
}

function renderSearchResults(filter = '') {
    const results = document.getElementById('search-results');
    if (!results) return;

    const query = filter.trim().toLowerCase();
    results.innerHTML = '';

    const matches = historyCache
        .filter(item => item.title.toLowerCase().includes(query))
        .slice(0, 20);

    matches.forEach(item => {
        const li = document.createElement('li');
        const title = document.createElement('div');
        title.className = 'result-title';
        title.textContent = item.title;

        const meta = document.createElement('div');
        meta.className = 'result-meta';
        meta.textContent = item.createdAt ? new Date(item.createdAt).toLocaleString() : '';

        li.appendChild(title);
        li.appendChild(meta);
        li.onclick = () => {
            closeSearchModal();
            loadConversation(item.id);
        };

        results.appendChild(li);
    });

    if (matches.length === 0) {
        const empty = document.createElement('li');
        empty.className = 'result-meta';
        empty.textContent = 'No conversations found';
        results.appendChild(empty);
    }
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

    // Cache for search
    historyCache = Object.entries(data).map(([id, item]) => ({
        id,
        title: item.title || "Untitled",
        createdAt: item.created_at || null,
    }));

    const historyList = document.getElementById("history-list");
    historyList.innerHTML = "";

    historyCache.forEach(({ id, title, createdAt }) => {
        const li = document.createElement("li");
        const titleEl = document.createElement("div");
        titleEl.className = "history-title";
        titleEl.textContent = title || "Untitled";

        const metaEl = document.createElement("div");
        metaEl.className = "history-meta";
        metaEl.textContent = createdAt
            ? `${new Date(createdAt).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`
            : "";

        li.appendChild(titleEl);
        li.appendChild(metaEl);
        li.onclick = () => loadConversation(id);
        historyList.appendChild(li);
    });
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
                if (msg.role === "user") {
                    appendMessage("user", msg.content || "");
                } else if (msg.role === "bot") {
                    const formatted = marked.parse(msg.content || "");
                    appendMessage("bot", formatted, { isHtml: true });
                }
            });
        } else if (data.messages[0].user) {
            // Old format with user/bot fields
            data.messages.forEach(msg => {
                appendMessage("user", msg.user || "");
                const botFormatted = marked.parse(msg.bot || "");
                appendMessage("bot", botFormatted, { isHtml: true });
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
        newChatBtn.addEventListener('click', createNewChat);
    }

    const menuBtns = document.querySelectorAll('.sidebar-menu');
    menuBtns.forEach((menuBtn) => {
        menuBtn.addEventListener('click', toggleSidebar);
    });

    const sidebarSearch = document.getElementById('sidebar-search');
    if (sidebarSearch) {
        sidebarSearch.addEventListener('click', () => {
            openSearchModal();
        });
    }

    const collapsedSearch = document.querySelector('.collapsed-search');
    if (collapsedSearch) {
        collapsedSearch.addEventListener('click', () => {
            openSearchModal();
        });
    }

    const collapsedNew = document.querySelector('.collapsed-new');
    if (collapsedNew) {
        collapsedNew.addEventListener('click', () => {
            setSidebarCollapsed(true);
            sidebarPinnedOpen = false;
            createNewChat();
        });
    }

    // No auto collapse on mouse leave: sidebar stays in chosen state.

    loadHistory();

    const searchQuery = document.getElementById('search-query');
    if (searchQuery) {
        searchQuery.addEventListener('input', (event) => {
            renderSearchResults(event.target.value);
        });

        searchQuery.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                const results = document.querySelector('#search-results li');
                if (results) results.click();
            }
            if (event.key === 'Escape') {
                closeSearchModal();
            }
        });
    }
};