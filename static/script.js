let currentSessionId = null;
let conversationStarted = false;
let sidebarPinnedOpen = false;
let historyCache = [];
let waitingTextIntervalId = null;
let titleLoadingIntervalId = null;
let inputPlaceholderIntervalId = null;
let initialPlaceholderTimeoutId = null;
let historyXScrollbarTimeoutId = null;
let chatScrollbarTimeoutId = null;
let currentConversationTitle = "New Conversation";
let renameModalSessionId = null;
let currentHistoryDeleteConfirmLi = null;
let titlebarDeleteConfirming = false;

function logClientError(label, details) {
    console.error(`[client-error] ${label}`, details || "");
}

function logServerResponseError(label, response, bodyText, parsedBody) {
    console.error(`[server-error] ${label}`, {
        status: response.status,
        statusText: response.statusText,
        ok: response.ok,
        body: bodyText,
        parsedBody,
    });
}

window.addEventListener("error", (event) => {
    logClientError("window.error", {
        message: event.message,
        source: event.filename,
        line: event.lineno,
        column: event.colno,
        stack: event.error ? event.error.stack : undefined,
    });
});

window.addEventListener("unhandledrejection", (event) => {
    logClientError("window.unhandledrejection", {
        reason: event.reason,
    });
});

const waitingMessages = [
    "Overclocking my brain... hang tight while I find those specs!",
    "Lexa is currently deep in the database. Don't close the lid just yet!",
    "Booting up your options...",
    "Spinning up the hard drive... yes, we still have one of those.",
    "Fetching results faster than your last Windows update. Promise.",
    "Lexa is connecting the dots — there are a lot of dots.",
    "Hold on, teaching the hamsters to run faster...",
    "Compiling awesomeness. This may take 3–5 business milliseconds.",
    "Rummaging through the cloud... it's bigger than it looks.",
    "Good things take time. Great things take slightly longer. Almost there.",
    "Lexa spotted your answer — she's just untangling the cables.",
    "Loading... because even robots need a moment to think.",
    "We're not buffering. We're being thorough.",
    "Asking the algorithm nicely. It said yes. Retrieving now.",
    "Your results are being hand-crafted by tiny digital elves.",
    "Lexa is putting on her thinking cap. It has RGB lighting.",
    "404 boredom not found — we'll be right with you!",
    "Running at the speed of caffeine. One sec.",
    "Please enjoy this brief intermission while Lexa does her thing.",
];

const waitingTitleMessages = [
    "Lexa is choosing her words carefully...",
    "Searching for the perfect title...",
    "Consulting the council of catchy names...",
    "Shaking the magic 8-ball for a title...",
    "Flipping through the thesaurus...",
    "Running titles through the vibe check...",
    "Summoning the muse...",
    "Please hold — naming things is hard.",
    "Almost something catchy...",
    "Words are being arranged...",
];

const initialInputPlaceholderMessages = [
    "Type something. Lexa is listening...",
    "What's on your mind?",
    "Ask me anything...",
    "Go ahead, don't be shy...",
    "Lexa is all ears...",
    "Start typing to get started...",
    "What are we building today?",
    "Your idea goes here...",
    "Hit me with it...",
    "Talk to Lexa...",
];

const initiatedInputPlaceholderMessages = [
    "Lexa is ready for your next move...",
    "What's next?",
    "Keep going...",
    "Your turn...",
    "Fire away...",
    "What else?",
    "Continue the thought...",
    "Lexa is waiting...",
    "Don't stop now...",
    "Next question?",
];

function pickRandomMessageFrom(messages, excludeIndex = -1) {
    if (!messages || !messages.length) {
        return { index: -1, text: "Loading..." };
    }

    let index = Math.floor(Math.random() * messages.length);
    if (messages.length > 1) {
        while (index === excludeIndex) {
            index = Math.floor(Math.random() * messages.length);
        }
    }

    return { index, text: messages[index] };
}

function startInputPlaceholderCycle(messages) {
    const inputField = document.getElementById("user-input");
    if (!inputField || !messages || !messages.length) return;

    if (inputPlaceholderIntervalId) {
        clearInterval(inputPlaceholderIntervalId);
        inputPlaceholderIntervalId = null;
    }

    let { index, text } = pickRandomMessageFrom(messages);
    inputField.placeholder = text;

    inputPlaceholderIntervalId = setInterval(() => {
        const picked = pickRandomMessageFrom(messages, index);
        index = picked.index;
        inputField.placeholder = picked.text;
    }, 2600);
}

function ensureAnimatedPlaceholderElement() {
    const inputArea = document.querySelector(".input-area");
    if (!inputArea) return null;

    let el = inputArea.querySelector(".animated-placeholder");
    if (el) return el;

    el = document.createElement("span");
    el.className = "animated-placeholder";
    inputArea.appendChild(el);
    return el;
}

function updateAnimatedPlaceholderVisibility() {
    const inputField = document.getElementById("user-input");
    const animatedEl = ensureAnimatedPlaceholderElement();
    if (!inputField || !animatedEl) return;

    const shouldShow = !conversationStarted && !inputField.value;
    animatedEl.classList.toggle("visible", shouldShow);
}

function stopInitialPlaceholderTypewriter() {
    if (initialPlaceholderTimeoutId) {
        clearTimeout(initialPlaceholderTimeoutId);
        initialPlaceholderTimeoutId = null;
    }
}

function startInitialPlaceholderTypewriter(messages) {
    const inputField = document.getElementById("user-input");
    const animatedEl = ensureAnimatedPlaceholderElement();
    if (!inputField || !animatedEl || !messages || !messages.length) return;

    stopInitialPlaceholderTypewriter();

    inputField.placeholder = "";
    let previousMessageIndex = -1;

    const runCycle = () => {
        if (conversationStarted) {
            updateAnimatedPlaceholderVisibility();
            return;
        }

        const picked = pickRandomMessageFrom(messages, previousMessageIndex);
        previousMessageIndex = picked.index;
        const message = picked.text;

        let charIndex = 0;

        const typeStep = () => {
            if (conversationStarted) return;

            animatedEl.textContent = message.slice(0, charIndex);
            updateAnimatedPlaceholderVisibility();

            if (charIndex < message.length) {
                charIndex += 1;
                initialPlaceholderTimeoutId = setTimeout(typeStep, 46);
                return;
            }

            initialPlaceholderTimeoutId = setTimeout(deleteStep, 1150);
        };

        const deleteStep = () => {
            if (conversationStarted) return;

            animatedEl.textContent = message.slice(0, charIndex);
            updateAnimatedPlaceholderVisibility();

            if (charIndex > 0) {
                charIndex -= 1;
                initialPlaceholderTimeoutId = setTimeout(deleteStep, 28);
                return;
            }

            initialPlaceholderTimeoutId = setTimeout(runCycle, 240);
        };

        typeStep();
    };

    runCycle();
}

function enterChatMode() {
    if (conversationStarted) return;
    conversationStarted = true;
    stopInitialPlaceholderTypewriter();
    const inputField = document.getElementById("user-input");
    if (inputField) {
        const picked = pickRandomMessageFrom(initiatedInputPlaceholderMessages);
        inputField.placeholder = picked.text;
    }
    updateAnimatedPlaceholderVisibility();

    const container = document.querySelector('.chat-container');
    container.classList.remove('centered');
    container.classList.add('in-conversation');

    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = 'none';
}

function setConversationTitle(title) {
    const normalized = (title || "New Conversation").trim() || "New Conversation";
    currentConversationTitle = normalized;
    const titleEl = document.getElementById("conversation-title");
    if (titleEl) {
        titleEl.textContent = normalized;
        titleEl.title = normalized;
    }
}

function clearTitleLoadingRemarks() {
    const titleEl = document.getElementById("conversation-title");
    if (titleLoadingIntervalId) {
        clearInterval(titleLoadingIntervalId);
        titleLoadingIntervalId = null;
    }
    if (titleEl) {
        titleEl.classList.remove("title-loading", "typing-reveal");
        titleEl.style.removeProperty("--typing-ch");
        const textEl = titleEl.querySelector(".title-loading-text");
        if (textEl) {
            textEl.classList.remove("typing-reveal");
            textEl.style.removeProperty("--typing-ch");
        }
    }
}

function setTitleLoadingText(titleEl, text) {
    if (!titleEl) return;
    let textEl = titleEl.querySelector(".title-loading-text");
    if (!textEl) {
        titleEl.textContent = "";
        textEl = document.createElement("span");
        textEl.className = "title-loading-text";
        titleEl.appendChild(textEl);
    }

    textEl.textContent = text;
    titleEl.title = text;
    textEl.style.setProperty("--typing-ch", `${Math.max(text.length + 4, 1)}ch`);
    textEl.classList.remove("typing-reveal");
    void textEl.offsetWidth;
    textEl.classList.add("typing-reveal");
}

function startTitleLoadingRemarks() {
    const titleEl = document.getElementById("conversation-title");
    if (!titleEl) return;

    clearTitleLoadingRemarks();
    titleEl.classList.add("title-loading");

    let { index, text } = pickRandomMessageFrom(waitingTitleMessages);
    setTitleLoadingText(titleEl, text);

    titleLoadingIntervalId = setInterval(() => {
        const picked = pickRandomMessageFrom(waitingTitleMessages, index);
        index = picked.index;
        setTitleLoadingText(titleEl, picked.text);
    }, 2400);
}

function createSpinnerIcon(extraClass = "") {
    const spinner = document.createElement("img");
    spinner.src = "/static/image/spinner-gap.svg";
    spinner.alt = "Loading";
    spinner.className = `spinner-icon ${extraClass}`.trim();
    return spinner;
}

function pickRandomWaitingMessage(excludeIndex = -1) {
    if (!waitingMessages.length) {
        return { index: -1, text: "Loading..." };
    }

    let index = Math.floor(Math.random() * waitingMessages.length);
    if (waitingMessages.length > 1) {
        while (index === excludeIndex) {
            index = Math.floor(Math.random() * waitingMessages.length);
        }
    }

    return { index, text: waitingMessages[index] };
}

function setRenameModalLoading(enabled) {
    const modal = document.getElementById("rename-modal");
    if (!modal) return;

    modal.classList.toggle("loading-state", enabled);
}

function openRenameLoadingOverlay() {
    const modal = document.getElementById("rename-modal");
    if (!modal) return;

    modal.classList.add("open");
    setRenameModalLoading(true);
}

function createHistoryLoadingItem() {
    const li = document.createElement("li");
    li.className = "history-loading-li";

    const spinner = createSpinnerIcon();
    const text = document.createElement("span");
    text.textContent = "Loading";

    li.appendChild(spinner);
    li.appendChild(text);
    return li;
}

function setHistoryActionLoadingState(li, enabled) {
    if (!li) return;

    const titleEl = li.querySelector(".history-title");
    const metaEl = li.querySelector(".history-meta");
    if (!titleEl) return;

    if (enabled) {
        if (!li.dataset.originalTitle) {
            li.dataset.originalTitle = titleEl.textContent || "Untitled";
        }

        titleEl.textContent = "loading";
        if (metaEl) {
            metaEl.textContent = "";
        }

        let spinnerWrap = li.querySelector(".history-action-spinner");
        if (!spinnerWrap) {
            spinnerWrap = document.createElement("div");
            spinnerWrap.className = "history-action-spinner";
            spinnerWrap.appendChild(createSpinnerIcon());
            li.appendChild(spinnerWrap);
        }

        li.classList.add("history-row-action-loading");
        return;
    }

    if (li.dataset.originalTitle) {
        titleEl.textContent = li.dataset.originalTitle;
        delete li.dataset.originalTitle;
    }

    li.classList.remove("history-row-action-loading");
}

function swapButtonIcon(button, src, alt) {
    if (!button) return;
    const icon = button.querySelector("img");
    if (!icon) return;

    const currentSrc = icon.getAttribute("src") || "";
    const currentAlt = icon.getAttribute("alt") || "";
    if (currentSrc === src && currentAlt === alt) return;

    if (button.__iconSwapOutTimeout) {
        clearTimeout(button.__iconSwapOutTimeout);
        button.__iconSwapOutTimeout = null;
    }

    if (button.__iconSwapInTimeout) {
        clearTimeout(button.__iconSwapInTimeout);
        button.__iconSwapInTimeout = null;
    }

    button.classList.remove("icon-swap-in");
    button.classList.add("icon-swap-out");

    button.__iconSwapOutTimeout = setTimeout(() => {
        icon.src = src;
        icon.alt = alt;

        button.classList.remove("icon-swap-out");
        button.classList.add("icon-swap-in");

        button.__iconSwapInTimeout = setTimeout(() => {
            button.classList.remove("icon-swap-in");
            button.__iconSwapInTimeout = null;
        }, 180);
        button.__iconSwapOutTimeout = null;
    }, 120);
}

async function saveConversationTitle(sessionId, title) {
    const response = await fetch(`/history/${sessionId}/title`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ title })
    });

    if (!response.ok) {
        throw new Error("Unable to update conversation title");
    }

    return response.json();
}

async function deleteConversationById(sessionId) {
    const response = await fetch(`/history/${sessionId}`, {
        method: "DELETE"
    });

    if (!response.ok) {
        throw new Error("Unable to delete conversation");
    }

    return response.json();
}

async function handleDeleteConversation(sessionId) {
    if (!sessionId) return;

    await deleteConversationById(sessionId);

    if (currentSessionId === sessionId) {
        await createNewChat();
        return;
    }

    await loadHistory();
}

function setHistoryDeleteConfirmMode(li, enabled) {
    if (!li) return;

    const deleteBtn = li.querySelector(".history-delete-btn");
    const editBtn = li.querySelector(".history-edit-btn");
    const deleteIcon = deleteBtn ? deleteBtn.querySelector("img") : null;
    const editIcon = editBtn ? editBtn.querySelector("img") : null;
    if (!deleteBtn || !editBtn || !deleteIcon || !editIcon) return;

    if (enabled) {
        li.classList.add("confirming-delete");
        deleteBtn.setAttribute("aria-label", "Confirm Delete Conversation");
        editBtn.setAttribute("aria-label", "Cancel Delete Conversation");
        swapButtonIcon(deleteBtn, "/static/image/check.svg", "Confirm Delete");
        swapButtonIcon(editBtn, "/static/image/x.svg", "Cancel");
        currentHistoryDeleteConfirmLi = li;
        return;
    }

    li.classList.remove("confirming-delete");
    deleteBtn.setAttribute("aria-label", "Delete Conversation");
    editBtn.setAttribute("aria-label", "Edit Conversation");
    swapButtonIcon(deleteBtn, "/static/image/trash-simple.svg", "Delete");
    swapButtonIcon(editBtn, "/static/image/pencil-simple-line.svg", "Edit");

    if (currentHistoryDeleteConfirmLi === li) {
        currentHistoryDeleteConfirmLi = null;
    }
}

function setTitlebarDeleteConfirmMode(enabled) {
    const deleteBtn = document.getElementById("conversation-delete");
    const editBtn = document.getElementById("conversation-edit");
    const deleteIcon = deleteBtn ? deleteBtn.querySelector("img") : null;
    const editIcon = editBtn ? editBtn.querySelector("img") : null;
    if (!deleteBtn || !editBtn || !deleteIcon || !editIcon) return;

    if (enabled) {
        titlebarDeleteConfirming = true;
        deleteBtn.setAttribute("aria-label", "Confirm Delete Conversation");
        editBtn.setAttribute("aria-label", "Cancel Delete Conversation");
        swapButtonIcon(deleteBtn, "/static/image/check.svg", "Confirm Delete");
        swapButtonIcon(editBtn, "/static/image/x.svg", "Cancel");
        return;
    }

    titlebarDeleteConfirming = false;
    deleteBtn.setAttribute("aria-label", "Delete Conversation");
    editBtn.setAttribute("aria-label", "Edit Conversation Title");
    swapButtonIcon(deleteBtn, "/static/image/trash-simple.svg", "Delete");
    swapButtonIcon(editBtn, "/static/image/pencil-simple-line.svg", "Edit");
}

function openRenameModal(sessionId, currentTitle = "") {
    if (!sessionId) return;

    const modal = document.getElementById("rename-modal");
    const input = document.getElementById("rename-input");
    if (!modal || !input) return;

    renameModalSessionId = sessionId;
    setRenameModalLoading(false);
    input.value = (currentTitle || "").trim() || "Untitled";

    modal.classList.add("open");
    setTimeout(() => {
        input.focus();
        input.select();
    }, 0);
}

function closeRenameModal() {
    const modal = document.getElementById("rename-modal");
    if (!modal) return;

    modal.classList.remove("open");
    modal.classList.remove("loading-state");
    renameModalSessionId = null;
}

async function submitRenameModal() {
    const input = document.getElementById("rename-input");
    if (!input || !renameModalSessionId) return;

    const cleanTitle = input.value.trim();
    if (!cleanTitle) return;

    setRenameModalLoading(true);

    try {
        await saveConversationTitle(renameModalSessionId, cleanTitle);

        if (currentSessionId === renameModalSessionId) {
            setConversationTitle(cleanTitle);
        }

        closeRenameModal();
        await loadHistory();
    } catch (error) {
        setRenameModalLoading(false);
        throw error;
    }
}

async function beginInlineHistoryRename(li, sessionId, currentTitle = "") {
    if (!li || li.classList.contains("editing-inline") || li.classList.contains("history-row-action-loading")) return;

    // Cancel delete confirmation mode before switching into rename mode.
    if (li.classList.contains("confirming-delete")) {
        setHistoryDeleteConfirmMode(li, false);
    }

    const titleEl = li.querySelector(".history-title");
    if (!titleEl) return;

    li.classList.add("editing-inline");

    const originalTitle = (currentTitle || titleEl.textContent || "Untitled").trim() || "Untitled";
    const input = document.createElement("input");
    input.type = "text";
    input.className = "history-inline-input";
    input.value = originalTitle;

    const editBtn = li.querySelector(".history-edit-btn");
    const editIcon = editBtn ? editBtn.querySelector("img") : null;
    if (editBtn) {
        editBtn.setAttribute("aria-label", "Save Conversation Title");
    }
    if (editIcon) {
        editIcon.src = "/static/image/paper-plane-right.svg";
        editIcon.alt = "Save";
    }

    titleEl.replaceWith(input);
    input.focus();
    input.select();

    let finished = false;
    const finish = async (commit) => {
        if (finished) return;
        finished = true;

        delete li.__finishInlineRename;

        if (editBtn) {
            editBtn.setAttribute("aria-label", "Edit Conversation");
        }
        if (editIcon) {
            editIcon.src = "/static/image/pencil-simple-line.svg";
            editIcon.alt = "Edit";
        }

        if (!commit) {
            input.replaceWith(titleEl);
            li.classList.remove("editing-inline");
            return;
        }

        const cleanTitle = input.value.trim();
        if (!cleanTitle || cleanTitle === originalTitle) {
            input.replaceWith(titleEl);
            li.classList.remove("editing-inline");
            return;
        }

        input.replaceWith(titleEl);
        li.classList.remove("editing-inline");
        setHistoryActionLoadingState(li, true);

        try {
            await saveConversationTitle(sessionId, cleanTitle);
            if (currentSessionId === sessionId) {
                setConversationTitle(cleanTitle);
            }
            await loadHistory();
        } catch (error) {
            logClientError("[inline rename] Failed to save title", error);
            setHistoryActionLoadingState(li, false);
            appendMessage("bot", "Unable to rename conversation right now.", { isError: true });
        }
    };

    li.__finishInlineRename = finish;

    input.addEventListener("click", (event) => event.stopPropagation());
    input.addEventListener("keydown", async (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            await finish(true);
        }

        if (event.key === "Escape") {
            event.preventDefault();
            await finish(false);
        }
    });

    input.addEventListener("blur", async () => {
        await finish(true);
    });
}

function appendMessage(role, content, options = {}) {
    const { isHtml = false, typing = false, id = null, isError = false } = options;
    const chatBox = document.getElementById("chat-box");
    if (!chatBox) return null;

    const row = document.createElement("div");
    row.className = `message-row ${role === "user" ? "message-user" : "message-bot"}`;
    if (typing) row.classList.add("typing");
    if (isError && role === "bot") row.classList.add("message-error");
    if (id) row.id = id;

    const avatar = document.createElement("img");
    avatar.className = "message-avatar";
    avatar.src = role === "user" ? "/static/image/user.svg" : "/static/image/logo-img.png";
    avatar.alt = role === "user" ? "User" : "Bot";

    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role === "user" ? "user-bubble" : "bot-bubble"}`;
    if (isError && role === "bot") {
        bubble.classList.add("error-bubble");
    }

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

function isErrorBotReply(text) {
    const reply = (text || "").trim();
    if (!reply) return false;

    const patterns = [
        /can't reach the gemini api/i,
        /can't access .* records/i,
        /^error connecting to server\.?$/i,
        /please retry in a few seconds/i,
        /^unable to (delete|rename|update|save)/i,
        /^lexa here\. i can't /i,
    ];

    return patterns.some((pattern) => pattern.test(reply));
}

function setWaitingText(waitingTextEl, text) {
    if (!waitingTextEl) return;
    waitingTextEl.textContent = text;
    waitingTextEl.style.setProperty("--typing-ch", `${Math.max(text.length, 1)}ch`);

    // Restart animation each time the status message changes.
    waitingTextEl.classList.remove("typing-reveal");
    void waitingTextEl.offsetWidth;
    waitingTextEl.classList.add("typing-reveal");
}

function createWaitingIndicator() {
    const chatBox = document.getElementById("chat-box");
    if (!chatBox) return null;

    const row = document.createElement("div");
    row.className = "message-row message-bot waiting-row";
    row.id = "typing-indicator";

    const avatar = document.createElement("img");
    avatar.className = "message-avatar";
    avatar.src = "/static/image/logo-img.png";
    avatar.alt = "Bot";

    const waitingText = document.createElement("div");
    waitingText.className = "waiting-text";

    const waitingSpinner = createSpinnerIcon("waiting-spinner");

    row.appendChild(avatar);
    row.appendChild(waitingSpinner);
    row.appendChild(waitingText);
    chatBox.appendChild(row);

    let { index, text } = pickRandomMessageFrom(waitingMessages);
    setWaitingText(waitingText, text);

    waitingTextIntervalId = setInterval(() => {
        const picked = pickRandomMessageFrom(waitingMessages, index);
        index = picked.index;
        setWaitingText(waitingText, picked.text);
    }, 2400);

    return row;
}

function clearWaitingIndicator() {
    if (waitingTextIntervalId) {
        clearInterval(waitingTextIntervalId);
        waitingTextIntervalId = null;
    }

    const waitingRow = document.getElementById("typing-indicator");
    if (waitingRow) waitingRow.remove();
}

async function sendMessage() {
    enterChatMode();

    const inputField = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const button = document.getElementById("send-btn");

    const userMessage = inputField.value.trim();
    if (!userMessage) return;

    const shouldShowTitleLoading = !currentConversationTitle || currentConversationTitle === "New Conversation";

    // Display user message as a right-aligned chat bubble.
    appendMessage("user", userMessage);

    inputField.value = "";
    inputField.disabled = true;
    button.disabled = true;

    // Add rotating waiting status indicator (no bubble container).
    createWaitingIndicator();

    if (shouldShowTitleLoading) {
        startTitleLoadingRemarks();
    }

    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ message: userMessage, session_id: currentSessionId })
        });

        const rawBody = await response.text();
        let data = null;
        try {
            data = rawBody ? JSON.parse(rawBody) : {};
        } catch (parseError) {
            logServerResponseError("/chat returned non-JSON body", response, rawBody.slice(0, 500), null);
            throw parseError;
        }

        if (!response.ok) {
            const serverError = (data && (data.error || data.message)) || `HTTP ${response.status}`;
            logServerResponseError("/chat returned error response", response, rawBody.slice(0, 1000), data);
            throw new Error(serverError);
        }

        // Keep session tracking in sync (if server returns it)
        if (data.session_id) {
            currentSessionId = data.session_id;
        }

        // Apply auto-generated server title as soon as it is available.
        if (data.title) {
            setConversationTitle(data.title);
            clearTitleLoadingRemarks();
        } else if (shouldShowTitleLoading) {
            setConversationTitle("New Conversation");
            clearTitleLoadingRemarks();
        }

        // Remove waiting indicator once response arrives.
        clearWaitingIndicator();

        // Show bot reply (render markdown if present)
        const replyText = data.reply || "";
        const formattedReply = marked.parse(replyText);
        appendMessage("bot", formattedReply, {
            isHtml: true,
            isError: isErrorBotReply(replyText),
        });

        // Refresh history to show updated title (generated after first few messages)
        loadHistory();

    } catch (error) {
        logClientError("[sendMessage] Fetch /chat failed", error);
        clearWaitingIndicator();
        if (shouldShowTitleLoading) {
            setConversationTitle("New Conversation");
            clearTitleLoadingRemarks();
        }
        appendMessage("bot", "Error connecting to server.", { isError: true });
    }

    inputField.disabled = false;
    button.disabled = false;
    inputField.focus();
    chatBox.scrollTop = chatBox.scrollHeight;
}

function applyNewChatUIState() {
    conversationStarted = false;
    if (inputPlaceholderIntervalId) {
        clearInterval(inputPlaceholderIntervalId);
        inputPlaceholderIntervalId = null;
    }
    startInitialPlaceholderTypewriter(initialInputPlaceholderMessages);
    clearTitleLoadingRemarks();
    setTitlebarDeleteConfirmMode(false);
    currentHistoryDeleteConfirmLi = null;

    const container = document.querySelector('.chat-container');
    container.classList.add('centered');
    container.classList.remove('in-conversation');

    const welcome = document.getElementById('welcome');
    if (welcome) welcome.style.display = '';

    const chatBox = document.getElementById("chat-box");
    if (chatBox) chatBox.innerHTML = "";

    const inputField = document.getElementById("user-input");
    if (inputField) {
        inputField.value = "";
        inputField.disabled = false;
    }
    updateAnimatedPlaceholderVisibility();

    const sendButton = document.getElementById("send-btn");
    if (sendButton) sendButton.disabled = false;

    setConversationTitle("New Conversation");

    clearWaitingIndicator();

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
        logClientError("[createNewChat] Fetch /reset failed", error);
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

    // Clear compact scrolled header mode when sidebar is manually toggled.
    if (collapsed) {
        sidebar.classList.remove('compact-history-top');
    }
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
    const historyList = document.getElementById("history-list");
    historyList.innerHTML = "";
    historyList.appendChild(createHistoryLoadingItem());

    const response = await fetch("/history");
    const data = await response.json();

    // Cache for search
    historyCache = Object.entries(data)
        .map(([id, item]) => ({
            id,
            title: item.title || "Untitled",
            createdAt: item.created_at || null,
        }))
        .sort((a, b) => {
            const aTime = a.createdAt ? new Date(a.createdAt).getTime() : 0;
            const bTime = b.createdAt ? new Date(b.createdAt).getTime() : 0;
            return bTime - aTime;
        });

    historyList.innerHTML = "";
    currentHistoryDeleteConfirmLi = null;

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

        const deleteBtn = document.createElement("button");
        deleteBtn.className = "history-delete-btn";
        deleteBtn.setAttribute("aria-label", "Delete Conversation");
        deleteBtn.innerHTML = '<img src="/static/image/trash-simple.svg" alt="Delete" />';
        deleteBtn.addEventListener("click", async (event) => {
            event.stopPropagation();
            if (li.classList.contains("editing-inline") || li.classList.contains("history-row-action-loading")) {
                return;
            }

            if (currentHistoryDeleteConfirmLi && currentHistoryDeleteConfirmLi !== li) {
                setHistoryDeleteConfirmMode(currentHistoryDeleteConfirmLi, false);
            }

            if (!li.classList.contains("confirming-delete")) {
                setHistoryDeleteConfirmMode(li, true);
                return;
            }

            try {
                setHistoryDeleteConfirmMode(li, false);
                setHistoryActionLoadingState(li, true);
                await handleDeleteConversation(id);
            } catch (error) {
                logClientError("[history delete] Failed to delete conversation", error);
                setHistoryActionLoadingState(li, false);
                appendMessage("bot", "Unable to delete conversation right now.", { isError: true });
            }
        });

        const editBtn = document.createElement("button");
        editBtn.className = "history-edit-btn";
        editBtn.setAttribute("aria-label", "Edit Conversation");
        editBtn.innerHTML = '<img src="/static/image/pencil-simple-line.svg" alt="Edit" />';
        editBtn.addEventListener("click", async (event) => {
            event.stopPropagation();

            if (li.classList.contains("history-row-action-loading")) {
                return;
            }

            if (li.classList.contains("confirming-delete")) {
                setHistoryDeleteConfirmMode(li, false);
                return;
            }

            if (li.classList.contains("editing-inline") && typeof li.__finishInlineRename === "function") {
                await li.__finishInlineRename(true);
                return;
            }
            await beginInlineHistoryRename(li, id, title);
        });

        li.appendChild(titleEl);
        li.appendChild(metaEl);
        li.appendChild(deleteBtn);
        li.appendChild(editBtn);
        li.onclick = () => loadConversation(id, title);
        historyList.appendChild(li);

        if (currentSessionId && currentSessionId === id) {
            setConversationTitle(title);
        }
    });
}

async function loadConversation(sessionId, title = null) {
    enterChatMode();
    setTitlebarDeleteConfirmMode(false);
    currentSessionId = sessionId;
    if (title) {
        setConversationTitle(title);
    }

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
                    appendMessage("bot", formatted, {
                        isHtml: true,
                        isError: isErrorBotReply(msg.content || ""),
                    });
                }
            });
        } else if (data.messages[0].user) {
            // Old format with user/bot fields
            data.messages.forEach(msg => {
                appendMessage("user", msg.user || "");
                const botFormatted = marked.parse(msg.bot || "");
                appendMessage("bot", botFormatted, {
                    isHtml: true,
                    isError: isErrorBotReply(msg.bot || ""),
                });
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
    inputField.addEventListener('input', () => {
        updateAnimatedPlaceholderVisibility();
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

    const scrolledSearch = document.querySelector('.scrolled-search');
    if (scrolledSearch) {
        scrolledSearch.addEventListener('click', () => {
            openSearchModal();
        });
    }

    const scrolledNew = document.querySelector('.scrolled-new');
    if (scrolledNew) {
        scrolledNew.addEventListener('click', () => {
            createNewChat();
        });
    }

    const conversationEdit = document.getElementById('conversation-edit');
    if (conversationEdit) {
        conversationEdit.addEventListener('click', async () => {
            if (!currentSessionId) return;

            if (titlebarDeleteConfirming) {
                setTitlebarDeleteConfirmMode(false);
                return;
            }

            openRenameModal(currentSessionId, currentConversationTitle);
        });
    }

    const conversationDelete = document.getElementById('conversation-delete');
    if (conversationDelete) {
        conversationDelete.addEventListener('click', async () => {
            if (!currentSessionId) return;

            if (!titlebarDeleteConfirming) {
                setTitlebarDeleteConfirmMode(true);
                return;
            }

            try {
                openRenameLoadingOverlay();
                await handleDeleteConversation(currentSessionId);
            } catch (error) {
                logClientError("[titlebar delete] Failed to delete conversation", error);
                appendMessage("bot", "Unable to delete conversation right now.", { isError: true });
            } finally {
                closeRenameModal();
                setTitlebarDeleteConfirmMode(false);
            }
        });
    }

    const renameCancel = document.getElementById('rename-cancel');
    if (renameCancel) {
        renameCancel.addEventListener('click', () => {
            closeRenameModal();
        });
    }

    const renameSave = document.getElementById('rename-save');
    if (renameSave) {
        renameSave.addEventListener('click', async () => {
            try {
                await submitRenameModal();
            } catch (error) {
                logClientError("[renameSave] submitRenameModal failed", error);
                appendMessage("bot", "Unable to rename conversation right now.", { isError: true });
            }
        });
    }

    const renameInput = document.getElementById('rename-input');
    if (renameInput) {
        renameInput.addEventListener('keydown', async (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                try {
                    await submitRenameModal();
                } catch (error) {
                    logClientError("[renameInput Enter] submitRenameModal failed", error);
                    appendMessage("bot", "Unable to rename conversation right now.", { isError: true });
                }
            }

            if (event.key === 'Escape') {
                closeRenameModal();
            }
        });
    }

    const historyPanel = document.querySelector('.history-panel');
    const historyList = document.getElementById('history-list');
    if (historyPanel && historyList) {
        historyList.addEventListener('scroll', () => {
            const shouldCompactTop = historyList.scrollTop > 18 && !historyPanel.classList.contains('collapsed');
            historyPanel.classList.toggle('compact-history-top', shouldCompactTop);

            historyPanel.classList.add('show-x-scroll');
            if (historyXScrollbarTimeoutId) {
                clearTimeout(historyXScrollbarTimeoutId);
            }

            historyXScrollbarTimeoutId = setTimeout(() => {
                historyPanel.classList.remove('show-x-scroll');
                historyXScrollbarTimeoutId = null;
            }, 900);
        });
    }

    const chatContainer = document.querySelector('.chat-container');
    const chatBox = document.getElementById('chat-box');
    if (chatContainer && chatBox) {
        chatBox.addEventListener('scroll', () => {
            chatContainer.classList.add('show-chat-scroll');
            if (chatScrollbarTimeoutId) {
                clearTimeout(chatScrollbarTimeoutId);
            }

            chatScrollbarTimeoutId = setTimeout(() => {
                chatContainer.classList.remove('show-chat-scroll');
                chatScrollbarTimeoutId = null;
            }, 900);
        });
    }

    // No auto collapse on mouse leave: sidebar stays in chosen state.

    if (inputPlaceholderIntervalId) {
        clearInterval(inputPlaceholderIntervalId);
        inputPlaceholderIntervalId = null;
    }
    startInitialPlaceholderTypewriter(initialInputPlaceholderMessages);
    updateAnimatedPlaceholderVisibility();

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