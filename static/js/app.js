// ========== State ==========
let currentSessionId = null;
let isProcessing = false;

// ========== DOM Elements ==========
const viewWelcome = document.getElementById('view-welcome');
const viewLoading = document.getElementById('view-loading');
const viewChat = document.getElementById('view-chat');

const repoUrlInput = document.getElementById('repo-url');
const btnLoad = document.getElementById('btn-load');
const btnText = btnLoad.querySelector('.btn-text');
const btnSpinner = btnLoad.querySelector('.btn-spinner');

const loadingMessage = document.getElementById('loading-message');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');

const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const btnNewRepo = document.getElementById('btn-new-repo');
const repoNameDisplay = document.getElementById('repo-name-display');

// ========== View Switching ==========
function showView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(viewId);
    target.classList.add('active');
}

// ========== Welcome View Logic ==========
btnLoad.addEventListener('click', handleLoadRepo);

repoUrlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleLoadRepo();
});

async function handleLoadRepo() {
    const repoUrl = repoUrlInput.value.trim();
    if (!repoUrl) {
        repoUrlInput.focus();
        repoUrlInput.style.borderColor = 'var(--error)';
        setTimeout(() => { repoUrlInput.style.borderColor = ''; }, 1500);
        return;
    }

    if (isProcessing) return;
    isProcessing = true;

    // Show loading state on button
    btnText.classList.add('hidden');
    btnSpinner.classList.remove('hidden');
    btnLoad.disabled = true;

    try {
        const response = await fetch('/api/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_url: repoUrl })
        });

        if (!response.ok) {
            throw new Error('Failed to start repository loading');
        }

        const data = await response.json();
        currentSessionId = data.session_id;

        // Switch to loading view
        showView('view-loading');
        resetLoadingView();
        startPolling(currentSessionId);

    } catch (err) {
        console.error('Error loading repo:', err);
        addChatMessage('ai', 'Error: Could not start loading the repository. Please check the URL and try again.');
        btnLoad.disabled = false;
        btnText.classList.remove('hidden');
        btnSpinner.classList.add('hidden');
        isProcessing = false;
    }
}

// ========== Loading / Polling Logic ==========
function resetLoadingView() {
    progressFill.style.width = '0%';
    progressText.textContent = '0%';
    loadingMessage.textContent = 'Preparing your workspace...';

    document.querySelectorAll('.step').forEach(step => {
        step.classList.remove('active', 'completed');
    });
}

let pollInterval = null;

function startPolling(sessionId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/status/${sessionId}`);
            const data = await response.json();

            updateLoadingView(data);

            if (data.status === 'ready') {
                clearInterval(pollInterval);
                pollInterval = null;
                onRepoReady(data);
            } else if (data.status === 'error') {
                clearInterval(pollInterval);
                pollInterval = null;
                onRepoError(data);
            }
        } catch (err) {
            console.error('Polling error:', err);
        }
    }, 1000);
}

function updateLoadingView(data) {
    const { status, message, progress } = data;

    // Update message
    if (message) loadingMessage.textContent = message;

    // Update progress
    if (progress !== undefined && progress !== null) {
        progressFill.style.width = `${progress}%`;
        progressText.textContent = `${progress}%`;
    }

    // Update step indicators
    const steps = ['cloning', 'indexing', 'building'];
    const currentStepIndex = steps.indexOf(status);

    steps.forEach((stepName, index) => {
        const stepEl = document.querySelector(`.step[data-step="${stepName}"]`);
        if (!stepEl) return;

        stepEl.classList.remove('active', 'completed');

        if (index < currentStepIndex) {
            stepEl.classList.add('completed');
        } else if (index === currentStepIndex) {
            stepEl.classList.add('active');
        }
    });
}

function onRepoReady(data) {
    isProcessing = false;
    repoNameDisplay.textContent = data.repo_name || 'Repository';

    // Add welcome message
    chatMessages.innerHTML = '';
    addChatMessage('ai', `Repository **${data.repo_name || ''}** has been loaded successfully! You can now ask questions about the codebase. Try asking about the project structure, specific functions, or how something works.`);

    // Switch to chat view
    showView('view-chat');
    chatInput.focus();
}

function onRepoError(data) {
    isProcessing = false;
    loadingMessage.textContent = data.message || 'An error occurred';
    progressFill.style.width = '0%';
    progressFill.style.background = 'var(--error)';
    progressText.textContent = '✕';

    // Show back button
    setTimeout(() => {
        if (confirm('Failed to load repository. Go back and try again?')) {
            showView('view-welcome');
            resetWelcomeButton();
        }
    }, 1500);
}

function resetWelcomeButton() {
    btnLoad.disabled = false;
    btnText.classList.remove('hidden');
    btnSpinner.classList.add('hidden');
}

// ========== Chat Logic ==========
chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendMessage();
    }
});

btnSend.addEventListener('click', handleSendMessage);

async function handleSendMessage() {
    const question = chatInput.value.trim();
    if (!question || !currentSessionId || isProcessing) return;

    isProcessing = true;
    chatInput.value = '';
    setSendButtonState(false);

    // Show user message
    addChatMessage('user', question);

    // Show typing indicator
    const typingId = addTypingIndicator();

    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                question: question,
                session_id: currentSessionId
            })
        });

        const data = await response.json();

        // Remove typing indicator
        removeTypingIndicator(typingId);

        if (data.status === 'success') {
            addChatMessage('ai', data.answer);
        } else {
            addChatMessage('ai', `**Error:** ${data.message || 'Something went wrong. Please try again.'}`);
        }

    } catch (err) {
        removeTypingIndicator(typingId);
        addChatMessage('ai', '**Error:** Could not reach the server. Please check if the backend is running.');
        console.error('Ask error:', err);
    } finally {
        isProcessing = false;
        setSendButtonState(true);
        chatInput.focus();
    }
}

// ========== Chat UI Helpers ==========
function addChatMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? 'U' : 'AI';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (role === 'ai') {
        // Parse markdown for AI messages
        contentDiv.innerHTML = marked.parse(content);
        // Highlight code blocks
        contentDiv.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });
    } else {
        contentDiv.textContent = content;
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);

    scrollToBottom();
    return messageDiv;
}

function addTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai';
    messageDiv.id = 'typing-indicator';

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = 'AI';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.innerHTML = '<div class="dot"></div><div class="dot"></div><div class="dot"></div>';

    contentDiv.appendChild(typingDiv);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);

    scrollToBottom();
    return 'typing-indicator';
}

function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function setSendButtonState(enabled) {
    if (enabled) {
        btnSend.classList.remove('disabled');
    } else {
        btnSend.classList.add('disabled');
    }
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

// ========== New Repository ==========
btnNewRepo.addEventListener('click', () => {
    currentSessionId = null;
    isProcessing = false;
    chatMessages.innerHTML = '';
    repoUrlInput.value = '';
    resetWelcomeButton();
    showView('view-welcome');
    repoUrlInput.focus();
});

// ========== Cancel Loading ==========
const btnCancelLoading = document.getElementById('btn-cancel-loading');

btnCancelLoading?.addEventListener('click', () => {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
    isProcessing = false;
    currentSessionId = null;
    resetLoadingView();
    resetWelcomeButton();
    repoUrlInput.value = '';
    showView('view-welcome');
    repoUrlInput.focus();
});

// ========== Marked Configuration ==========
marked.setOptions({
    breaks: true,
    gfm: true,
    headerIds: false,
    mangle: false
});

// ========== Initialize ==========
showView('view-welcome');
