document.addEventListener('DOMContentLoaded', function () {
    // Inject Chat HTML if not present
    if (!document.getElementById('chat-widget')) {
        const chatHTML = `
        <div id="chat-widget" class="chat-widget-container">
            <!-- Chat Button -->
            <button id="chat-toggle" class="chat-fab" aria-label="Open Chat">
                <i class="bi bi-chat-dots-fill"></i>
            </button>

            <!-- Chat Window -->
            <div id="chat-window" class="chat-window">
                <!-- Header -->
                <div class="chat-header">
                    <div class="chat-avatar">
                        <i class="bi bi-robot"></i>
                    </div>
                    <div class="chat-info">
                        <h3>Visitor Assistant</h3>
                        <p>Online | Ready to help</p>
                    </div>
                    <div class="chat-actions">
                        <button id="chat-maximize" class="btn btn-sm btn-link text-white p-0 me-2" title="Maximize">
                            <i class="bi bi-arrows-angle-expand"></i>
                        </button>
                        <button id="chat-close" class="btn btn-sm btn-link text-white p-0">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                </div>

                <!-- Messages -->
                <div id="chat-messages" class="chat-messages">
                    <div class="message bot">
                        Hello! I'm your Visitor Assistant. How can I help you today?
                    </div>
                </div>

                <!-- Input Area -->
                <div class="chat-input-area">
                    <input type="text" id="chat-input" class="chat-input" placeholder="Type a message..." autocomplete="off">
                    <button id="chat-send" class="chat-send-btn">
                        <i class="bi bi-send-fill"></i>
                    </button>
                </div>
            </div>
        </div>
        `;
        document.body.insertAdjacentHTML('beforeend', chatHTML);
    }

    const toggleBtn = document.getElementById('chat-toggle');
    const closeBtn = document.getElementById('chat-close');
    const maximizeBtn = document.getElementById('chat-maximize');
    const chatWindow = document.getElementById('chat-window');
    const messagesContainer = document.getElementById('chat-messages');
    const inputField = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const icon = toggleBtn.querySelector('i');

    let isOpen = false;
    let isMaximized = false;

    // Toggle Chat
    function toggleChat() {
        isOpen = !isOpen;
        chatWindow.classList.toggle('open', isOpen);
        toggleBtn.classList.toggle('active', isOpen);

        if (isOpen) {
            icon.classList.replace('bi-chat-dots-fill', 'bi-x-lg');
            inputField.focus();
            scrollToBottom();
        } else {
            icon.classList.replace('bi-x-lg', 'bi-chat-dots-fill');
        }
    }

    toggleBtn.addEventListener('click', toggleChat);
    closeBtn.addEventListener('click', toggleChat);

    // Maximize Chat
    function toggleMaximize() {
        isMaximized = !isMaximized;
        chatWindow.classList.toggle('maximized', isMaximized);
        const maxIcon = maximizeBtn.querySelector('i');
        if (isMaximized) {
            maxIcon.classList.replace('bi-arrows-angle-expand', 'bi-arrows-angle-contract');
        } else {
            maxIcon.classList.replace('bi-arrows-angle-contract', 'bi-arrows-angle-expand');
        }
        scrollToBottom();
    }

    maximizeBtn.addEventListener('click', toggleMaximize);

    // Global Key Listeners
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isOpen) {
            toggleChat();
        }
    });

    // Send Message
    async function sendMessage() {
        const text = inputField.value.trim();
        if (!text) return;

        // Add User Message
        appendMessage(text, 'user');
        inputField.value = '';

        // Show Typing Indicator
        const typingId = showTypingIndicator();
        scrollToBottom();

        try {
            const response = await fetch('/chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: text })
            });

            const data = await response.json();

            // Remove Typing Indicator
            removeTypingIndicator(typingId);

            // Add Bot Response
            if (data.text) {
                appendMessage(data.text, 'bot');
            }

            // Add Actions if any
            if (data.actions && data.actions.length > 0) {
                appendActions(data.actions);
            }

        } catch (error) {
            console.error('Chat Error:', error);
            removeTypingIndicator(typingId);
            appendMessage("Sorry, I'm having trouble connecting right now.", 'bot');
        }

        scrollToBottom();
    }

    // Event Listeners for Sending
    sendBtn.addEventListener('click', sendMessage);
    inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // Helper Functions
    function appendMessage(text, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender}`;
        msgDiv.innerHTML = text; // Allow HTML for formatting
        messagesContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function appendActions(actions) {
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'bot-actions';

        actions.forEach(action => {
            const btn = document.createElement('a'); // Use anchor for links
            btn.className = 'action-btn';
            btn.textContent = action.text;
            btn.style.cursor = 'pointer';

            if (action.url) {
                btn.href = action.url;
            } else if (action.event) {
                // Support custom JS events (Drill-through)
                btn.href = "#";
                btn.onclick = (e) => {
                    e.preventDefault();
                    if (action.event === 'drillDown') {
                        // Advanced multi-filter support
                        const p = action.payload || {};
                        drillDownGlobal(p.search || '', p.status || '', p.days);
                    } else if (action.event === 'drillDownPurpose') {
                        drillDownGlobal(action.payload, '', null);
                    } else if (action.event === 'drillDownActive') {
                        drillDownGlobal('', 'IN', null);
                    } else if (action.event === 'drillDownDate') {
                        // Priority to local dashboard function if exists, else global API
                        if (typeof window.drillDownDate === 'function') {
                            window.drillDownDate(action.payload);
                        } else {
                            drillDownGlobal('', '', action.payload);
                        }
                    } else if (typeof window[action.event] === 'function') {
                        window[action.event](action.payload);
                    } else {
                        console.warn('Action not handled:', action.event);
                    }
                };
            } else if (action.action) {
                // Default text fallback
                btn.href = "#";
                btn.onclick = (e) => {
                    e.preventDefault();
                    // If it looks like a search query, just send it
                    if (action.action.startsWith('search ')) {
                        window.sendChatAction(action.action);
                    } else {
                        inputField.value = action.action;
                        document.getElementById('chat-send').click();
                    }
                };
            }

            actionsDiv.appendChild(btn);
        });

        messagesContainer.appendChild(actionsDiv);
        scrollToBottom();
    }

    // GLOBAL API-BASED DRILLDOWN
    async function drillDownGlobal(term, status, days) {
        let labelParts = [];
        if (status === 'IN') labelParts.push('Active');
        if (term) labelParts.push(term);

        let timePart = 'History';
        if (days === 0) timePart = "Today";
        else if (days === 1) timePart = "Yesterday";
        else if (days > 1) timePart = `Last ${days} Days`;

        labelParts.push(timePart);
        const label = labelParts.join(' ') + ' Visitors';

        if (window.openGlobalDrawer) {
            window.openGlobalDrawer(label, '<div class="text-center py-4"><div class="spinner-border text-primary" role="status"></div><div class="mt-2">Fetching data...</div></div>');
        }

        try {
            let url = `/api/visitors?limit=100`;
            if (term) url += `&search=${encodeURIComponent(term)}`;
            if (status) url += `&status=${status}`;
            if (days !== null && days !== undefined) url += `&days=${days}`;

            const res = await fetch(url);
            const visitors = await res.json();

            if (!visitors || visitors.length === 0) {
                if (window.openGlobalDrawer) window.openGlobalDrawer('No Results', '<div class="text-center py-4 text-muted">No visitors found matching your criteria.</div>');
                return;
            }

            let html = `
            <div class="d-flex justify-content-between align-items-center mb-3">
                 <span class="badge bg-primary rounded-pill">${visitors.length} Results</span>
            </div>
            <div class="list-group list-group-flush">
            `;

            visitors.forEach(v => {
                const checkIn = v.check_in ? new Date(v.check_in).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--';
                const name = v.visitor_name || 'Unknown';
                const initial = name[0].toUpperCase();
                const statusBadge = v.status === 'IN'
                    ? '<span class="badge bg-success-subtle text-success border border-success-subtle" style="font-size:0.65rem">ACTIVE</span>'
                    : '<span class="badge bg-light text-secondary border" style="font-size:0.65rem">OUT</span>';

                html += `
                <div class="list-group-item px-0 py-3 border-bottom">
                    <div class="d-flex align-items-center gap-3">
                        <div class="avatar-circle" style="min-width:40px; width:40px; height:40px; background:#4f46e5; color:white; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:bold;">
                            ${initial}
                        </div>
                        <div class="flex-grow-1">
                            <div class="d-flex justify-content-between">
                                <h6 class="mb-0 fw-bold text-dark">${name}</h6>
                                <small class="text-muted" style="font-size:0.75rem">${checkIn}</small>
                            </div>
                            <div class="small text-muted mb-1">${v.company || ''} &bull; ${v.person_to_meet || ''}</div>
                            ${statusBadge}
                        </div>
                    </div>
                </div>`;
            });
            html += '</div>';

            const title = status === 'IN' ? 'Active Visitors' : (term ? `Results: ${term}` : 'Visitors');
            if (window.openGlobalDrawer) window.openGlobalDrawer(title, html);

        } catch (e) {
            console.error(e);
            if (window.openGlobalDrawer) window.openGlobalDrawer('Error', '<div class="text-danger p-3">Failed to load data.</div>');
        }
    }

    function handleAction(actionType) {
        // Send a hidden message to trigger the bot's logic for this action
        if (actionType === 'stats') {
            inputField.value = "stats";
            sendMessage();
        } else if (actionType === 'help') {
            inputField.value = "help";
            sendMessage();
        }
    }

    function showTypingIndicator() {
        const id = 'typing-' + Date.now();
        const typingHTML = `
            <div id="${id}" class="message bot typing-indicator" style="display:flex; align-items:center; gap:4px; padding:12px 16px;">
                <div class="dot" style="width:6px; height:6px; background:#94a3b8; border-radius:50%; animation:typing 1.4s infinite ease-in-out both; animation-delay:-0.32s;"></div>
                <div class="dot" style="width:6px; height:6px; background:#94a3b8; border-radius:50%; animation:typing 1.4s infinite ease-in-out both; animation-delay:-0.16s;"></div>
                <div class="dot" style="width:6px; height:6px; background:#94a3b8; border-radius:50%; animation:typing 1.4s infinite ease-in-out both;"></div>
            </div>
        `;
        messagesContainer.insertAdjacentHTML('beforeend', typingHTML);
        return id;
    }

    function removeTypingIndicator(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Expose global action handler for injected HTML
    window.sendChatAction = function (text) {
        inputField.value = text;
        sendMessage();
    };
});
