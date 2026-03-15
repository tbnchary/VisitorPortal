# Visitor Assistant Chatbot Guide

The Visitor Management System now includes an intelligent **Visitor Assistant Chatbot**. This guide explains its features, architecture, and how to extend its capabilities.

## 🤖 Features

1.  **Instant Stats**: Ask for "stats", "status", or "how many visitors" to get real-time data on active visitors, today's check-ins, and total records.
2.  **Navigation Shortcuts**: The bot provides direct links ("actions") to important pages like "Add Visitor", "Visitor Logs", "Groups", "Export", and "Settings".
3.  **Interactive Actions**: Responses often include clickable buttons (e.g., "Show Stats", "Go to Registration") for faster interaction.
4.  **Glassmorphism UI**: A beautiful, modern interface with a floating action button (FAB) that sits unobtrusively in the corner.
5.  **Smart Context**: The bot recognizes greetings and common keywords like "add", "log", "export", and "help".

## 🛠️ Technical Architecture

### 1. Backend Logic (`app/chatbot_logic.py`)
This file contains the core intelligence.
-   `process_message(message, user_id)`: Analyzes user input and returns a JSON response.
-   `get_stats()`: Queries the database for real-time visitor counts.
-   It uses keyword matching to determine intent (e.g., "stats" -> fetch database counts).

### 2. API Endpoint (`app/routes.py`)
A new route `/chat/message` accepts POST requests with the user's message and returns the bot's response. It is protected by `@login_required`.

### 3. Frontend logic (`app/static/js/chat.js`)
-   Injects the chat widget HTML into the page.
-   Handles opening/closing the chat window.
-   Sends asynchronous `POST` requests to the backend.
-   Displays typing indicators and renders messages/buttons.

### 4. Styles (`app/static/css/chat.css`)
-   Contains all the styling for the widget, animations, and responsive design.

## 🚀 How to Extend

### Adding New Commands
To add a new command, edit `app/chatbot_logic.py`.

**Example: Adding a "Security" command**
1.  Open `app/chatbot_logic.py`.
2.  Add a new `if` block in `process_message`:

```python
    if "security" in message:
        return {
            "text": "For security incidents, please contact the main control room immediately at Ext 999.",
            "actions": [{"text": "Call Security", "url": "tel:999"}]
        }
```

### Customizing the UI
To change the colors or appearance, edit `app/static/css/chat.css`. the variables at the top (`:root`) control the main theme colors.

```css
:root {
    --chat-primary: #dc2626; /* Change to Red */
    /* ... */
}
```

## 📝 Usage
1.  Log in to the Visitor Portal.
2.  Click the blue "Chat" icon in the bottom-right corner.
3.  Type "details", "stats", "help", or "add visitor" to get started.
