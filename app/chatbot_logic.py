import re
import random
import traceback
from datetime import datetime, timedelta
from flask import url_for, session, current_app
from app.db import get_db
import string

# --- 🎨 ENTERPRISE THEME ---
THEME = {
    "primary": "#0f172a",    # Slate 900 (Corporate Dark)
    "accent": "#3b82f6",     # Blue 500
    "success": "#10b981",    # Emerald 500
    "warning": "#f59e0b",    # Amber 500
    "danger": "#ef4444",     # Red 500
    "bg": "#f8fafc",         # Slate 50
    "card_bg": "#ffffff",
    "text_main": "#1e293b",  # Slate 800
    "text_sub": "#64748b",   # Slate 500
    "border": "#e2e8f0"      # Slate 200
}

# --- 📚 KNOWLEDGE BASE ---
KNOWLEDGE_BASE = {
    "password": "To reset a password, please contact your system administrator or use the 'Forgot Password' link on the login page.",
    "export": "You can export data from the 'Visitor Logs' page. Look for the 'Export to CSV' specific button.",
    "printer": "Badges are automatically sent to the configured printer upon check-in. Ensure the printer is online.",
    "limit": "There is no hard limit on the number of visitors you can register daily.",
    "cloud": "This system operates on a secure local/cloud hybrid environment.",
    "scanner": "You can use the mobile scanner by navigating to the dashboard and clicking the QR icon.",
    "camera": "If the camera is not working, ensure you have allowed browser permissions and are using HTTPS or localhost.",
    "host": "You can search for visitors by their host name using the 'Find for [Host Name]' command.",
    "hours": "System operating hours are 24/7, but reception support is available 9 AM - 6 PM."
}

class VisitorBot:
    def __init__(self, message, user_id=None):
        self.raw_message = message
        self.message = message.lower().strip()
        self.user_id = user_id
        self.context = session.get('chat_context', {})
        
    def respond(self):
        try:
            # 1. Global Cancellations
            if self.message in ['cancel', 'stop', 'reset', 'menu', 'clear', 'back']:
                session.pop('chat_context', None)
                return self.ui_greeting("System Ready. How can I assist?")

            # 2. Context Handling
            ctx = self.context.get('state')
            if ctx == 'awaiting_search':
                session.pop('chat_context', None)
                return self.action_search(self.message)
            if ctx == 'awaiting_host_notify':
                 session.pop('chat_context', None)
                 return self.action_notify_host(self.message)

            # 3. Intent Analysis
            intent = self.classify_intent()
            
            # 4. Execution Routing
            if intent == 'GREETING':    return self.ui_greeting()
            if intent == 'STATS_SPECIFIC': return self.action_specific_stats(self.extract_term(['count', 'number', 'how many', 'of', 'for', 'in', 'total', 'stats', 'statistics', 'about', 'list', 'show me', 'visitors', 'visitor', 'logs', 'from']))
            if intent == 'INSIGHTS':    return self.action_insights()
            if intent == 'STATS':       return self.action_dashboard()
            if intent == 'SEARCH':      return self.action_search(self.extract_term(['search','find','look','check']))
            if intent == 'CHECKOUT':    return self.action_checkout(self.extract_term(['checkout','leave','exit']))
            if intent == 'ADD_VISITOR': return self.action_add_visitor(self.extract_term(['add', 'new', 'register', 'create', 'visitor', 'entry', 'log in']))
            if intent == 'EXPORT':      return self.action_export()
            if intent == 'NOTIFY':      return self.ui_notify_prompt()
            if intent == 'SECURITY':    return self.ui_security_alert()
            if intent == 'HELP':        return self.ui_greeting()
            if intent == 'KNOWLEDGE':   return self.action_knowledge_base()
            if intent == 'LATEST_LOGS': return self.action_latest_logs()
            if intent == 'WEATHER':     return self.action_weather()
            if intent == 'HOST_LOOKUP': return self.action_search_host(self.extract_term(['who is meeting', 'visiting', 'host']))
            if intent == 'QR_GEN':      return self.action_generate_qr(self.extract_term(['qr', 'pass', 'badge', 'code']))
            if intent == 'ROOM_STATUS': return self.action_room_management()
            if intent == 'SHED_STATUS': return self.action_shed_status()
            if intent == 'VIP':         return self.action_vip_protocol()
            if intent == 'LANGUAGE':    return self.action_language_greeting()
            if intent == 'ANNOUNCE':    return self.action_broadcast(self.extract_term(['announce', 'broadcast', 'say', 'tell everyone']))

            
            # Implicit Search Fallback
            
            # Implicit Search Fallback
            if len(self.message) > 2 and len(self.message.split()) < 4:
                return self.action_search(self.raw_message)

            return self.ui_fallback()

        except Exception as e:
            print(f"BOT ERROR: {e}")
            return {"text": "⚠️ System Malfunction. Please reset."}

    # --- 🧠 BRAIN ---
    def classify_intent(self):
        m = self.message
        
        # Regex based matching for higher accuracy
        if re.search(r'\b(hi|hello|hey|greetings|start|morning|afternoon|evening)\b', m): return 'GREETING'
        
        # Specific Count Check (Broader matching)
        # Specific Count Check (Broader matching)
        if re.search(r'\b(add|new|register|create|log in)\b', m) and 'visitor' in m: return 'ADD_VISITOR'
        
        # Priority: Export (if report/csv mentioned with date)
        if re.search(r'\b(export|download|csv|report|excel|sheet)\b', m): return 'EXPORT'

        if re.search(r'\b(meetings?|host|visiting)\b', m): return 'HOST_LOOKUP'

        # Specific Count Check (Broader matching)
        if re.search(r'\b(count|number|how many|stats?|statistics|data|active|today|yesterday|last \d+ days|visitors?)\b', m): return 'STATS_SPECIFIC'
        
        # Insights & Analytics
        if re.search(r'\b(top|most|busiest|peak|frequent|popular|trends|purpose|summary|weekly)\b', m): return 'INSIGHTS'
        
        if re.search(r'\b(stat|stats|traffic|chart|dashboard|analytics|numbers|metrics)\b', m): return 'STATS'
        if re.search(r'\b(find|search|locate|who is|look up|check|where)\b', m): return 'SEARCH'
        if re.search(r'\b(out|leave|depart|exit|checkout|sign out|log out)\b', m): return 'CHECKOUT'
        if re.search(r'\b(add|new|register|create|visitor|entry|log in)\b', m): return 'ADD_VISITOR'
        
        if re.search(r'\b(notify|message|tell|inform|alert host)\b', m): return 'NOTIFY'
        if re.search(r'\b(fire|emergency|alert|police|danger|help me|security)\b', m): return 'SECURITY'
        if re.search(r'\b(thanks|thank|cool|great|awesome|good job)\b', m): return 'THANKS'
        if re.search(r'\b(help|guide|option|menu|support|assist)\b', m): return 'HELP'
        if re.search(r'\b(latest|recent|logs|history|last few)\b', m): return 'LATEST_LOGS'
        if re.search(r'\b(weather|time|date|clock|temp|temperature)\b', m): return 'WEATHER'
        if re.search(r'\b(qr|pass|badge|code|entry pass)\b', m): return 'QR_GEN'
        if re.search(r'\b(room|meeting|conference|availability|book|block|lock)\b', m): return 'ROOM_STATUS'
        if re.search(r'\b(shed|storage|warehouse|bay|yard|customer shed)\b', m): return 'SHED_STATUS'
        if re.search(r'\b(vip|important|ceo|president|priority|special guest|feedback)\b', m): return 'VIP'
        if re.search(r'\b(hola|bonjour|namaste|ciao|hallo|guten tag)\b', m): return 'LANGUAGE'
        if re.search(r'\b(announce|broadcast|public address|paging)\b', m): return 'ANNOUNCE'
        
        # Knowledge Base Check
        if any(k in m for k in KNOWLEDGE_BASE.keys()): return 'KNOWLEDGE'
        
        return 'UNKNOWN'

    def extract_term(self, triggers):
        m = self.message
        # Remove primary trigger words
        for t in triggers: 
            m = re.sub(r'\b' + re.escape(t) + r's?\b', '', m, flags=re.IGNORECASE)
            
        # Remove specific command filler words
        stopwords = [
            'please', 'can', 'you', 'show', 'me', 'the', 'is', 'are', 'for', 'of', 'in', 'at', 'on',
            'what', 'details', 'info', 'about', 'total', 'count', 'from', 'form', 'with', 'by',
            'visitor', 'visitors', 'visit', 'visits', 'record', 'records', 'logs', 'list'
        ]
        
        for w in stopwords:
            m = re.sub(r'\b' + w + r'\b', '', m, flags=re.IGNORECASE)
            
        m = m.translate(str.maketrans('', '', string.punctuation))
        return m.strip()

    # --- 🎨 ENTERPRISE UI COMPONENTS ---
    
    def card(self, title, body, icon="", color=THEME['primary'], footer=""):
        return f"""
        <div style="background:{THEME['card_bg']}; border:1px solid {THEME['border']}; border-radius:8px; overflow:hidden; box-shadow:0 2px 4px rgba(0,0,0,0.03); margin-bottom:8px;">
            <div style="background:{color}; padding:8px 12px; display:flex; align-items:center;">
                <span style="font-size:14px; margin-right:8px;">{icon}</span>
                <span style="font-size:11px; font-weight:700; color:white; text-transform:uppercase; letter-spacing:0.5px;">{title}</span>
            </div>
            <div style="padding:12px; color:{THEME['text_main']}; font-size:13px; line-height:1.5;">{body}</div>
            {f'<div style="background:{THEME["bg"]}; padding:6px 12px; font-size:10px; color:{THEME["text_sub"]}; border-top:1px solid {THEME["border"]};">{footer}</div>' if footer else ''}
        </div>
        """

    def ui_main_menu(self, subtext="Professional Visitor Management"):
        body = f"""
        {subtext}<br><br>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
            <div onclick="window.sendChatAction('stats')" style="background:#f1f5f9; padding:8px; border-radius:6px; text-align:center; cursor:pointer; transition:0.2s; hover:background:#e2e8f0;">📊 Analytics</div>
            <div onclick="window.sendChatAction('add visitor')" style="background:#f1f5f9; padding:8px; border-radius:6px; text-align:center; cursor:pointer; transition:0.2s;">➕ Add Visitor</div>
            <div onclick="window.sendChatAction('latest logs')" style="background:#f1f5f9; padding:8px; border-radius:6px; text-align:center; cursor:pointer; transition:0.2s;">� Recent Logs</div>
            <div onclick="window.sendChatAction('search')" style="background:#f1f5f9; padding:8px; border-radius:6px; text-align:center; cursor:pointer; transition:0.2s;">� Search</div>
            <div onclick="window.sendChatAction('checkout')" style="background:#f1f5f9; padding:8px; border-radius:6px; text-align:center; cursor:pointer; transition:0.2s;">� Checkout</div>
            <div onclick="window.sendChatAction('weather')" style="background:#f1f5f9; padding:8px; border-radius:6px; text-align:center; cursor:pointer; transition:0.2s;">🌤️ Info</div>
        </div>
        """
        return {
            "text": self.card("Main Menu", body, "🏢", THEME['primary']),
            "actions": [{"text": "View Dashboard", "url": url_for("main.index")}]
        }
    
    def ui_greeting(self, override_text=None):
        # 1. Fetch Stats for Dashboard
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as c FROM visitors WHERE status='IN'")
        active = cursor.fetchone()['c']
        cursor.execute("SELECT COUNT(*) as c FROM visitors")
        total_visitors = cursor.fetchone()['c']
        today_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) as c FROM visitors WHERE DATE(check_in)=%s", (today_date,))
        today_count = cursor.fetchone()['c']
        conn.close()

        h = datetime.now().hour
        t = "Good Morning" if h<12 else "Good Afternoon" if h<17 else "Good Evening"
        welcome = override_text or f"<strong>{t}!</strong> I am your AI-powered system concierge. How can I assist you today?"
        
        # 2. Universal Portal Body
        body = f"""
        {welcome}<br><br>
        
        <!-- Live Stats Header -->
        <div style="display:flex; justify-content:space-between; text-align:center; margin-bottom:12px; gap:6px;">
             <div style="flex:1; background:#f8fafc; padding:8px 4px; border-radius:6px; border:1px solid #e2e8f0;">
                <div style="font-size:16px; font-weight:800; color:{THEME['accent']};">{active}</div>
                <div style="font-size:7px; color:{THEME['text_sub']}; font-weight:bold;">ACTIVE</div>
             </div>
             <div style="flex:1; background:#f8fafc; padding:8px 4px; border-radius:6px; border:1px solid #e2e8f0;">
                <div style="font-size:16px; font-weight:800; color:{THEME['text_main']};">{today_count}</div>
                <div style="font-size:7px; color:{THEME['text_sub']}; font-weight:bold;">TODAY</div>
             </div>
             <div style="flex:1; background:#f8fafc; padding:8px 4px; border-radius:6px; border:1px solid #e2e8f0;">
                <div style="font-size:16px; font-weight:800; color:{THEME['success']};">{total_visitors}</div>
                <div style="font-size:7px; color:{THEME['text_sub']}; font-weight:bold;">LOGS</div>
             </div>
        </div>

        <!-- Universal Action Grid -->
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:15px;">
            <div onclick="window.sendChatAction('add visitor')" style="background:{THEME['bg']}; padding:10px; border-radius:6px; text-align:center; cursor:pointer; font-size:12px; border:1px solid {THEME['border']}; transition:0.2s;">➕ New Entry</div>
            <div onclick="window.sendChatAction('latest logs')" style="background:{THEME['bg']}; padding:10px; border-radius:6px; text-align:center; cursor:pointer; font-size:12px; border:1px solid {THEME['border']};">📋 Recent Logs</div>
            <div onclick="window.sendChatAction('search')" style="background:{THEME['bg']}; padding:10px; border-radius:6px; text-align:center; cursor:pointer; font-size:12px; border:1px solid {THEME['border']};">🔍 Search List</div>
            <div onclick="window.sendChatAction('checkout')" style="background:{THEME['bg']}; padding:10px; border-radius:6px; text-align:center; cursor:pointer; font-size:12px; border:1px solid {THEME['border']};">🚪 Checkout</div>
            <div onclick="window.sendChatAction('qr pass')" style="background:{THEME['bg']}; padding:10px; border-radius:6px; text-align:center; cursor:pointer; font-size:12px; border:1px solid {THEME['border']};">🎟️ QR Pass</div>
            <div onclick="window.sendChatAction('report')" style="background:{THEME['bg']}; padding:10px; border-radius:6px; text-align:center; cursor:pointer; font-size:12px; border:1px solid {THEME['border']};">📊 Reports</div>
            <div onclick="window.sendChatAction('shed status')" style="background:{THEME['bg']}; padding:10px; border-radius:6px; text-align:center; cursor:pointer; font-size:12px; border:1px solid {THEME['border']};">🏭 Sheds</div>
            <div onclick="window.sendChatAction('meeting rooms')" style="background:{THEME['bg']}; padding:10px; border-radius:6px; text-align:center; cursor:pointer; font-size:12px; border:1px solid {THEME['border']};">🏢 Rooms</div>
        </div>

        <!-- Examples Section -->
        <div style="font-size:10px; color:{THEME['text_sub']}; font-weight:bold; margin-bottom:8px; text-transform:uppercase;">💡 Try Asking:</div>
        <div style="display:flex; gap:6px; overflow-x:auto; padding-bottom:10px; margin-bottom:5px;">
            <div onclick="window.sendChatAction('visitors today')" style="background:white; border:1px solid {THEME['accent']}; color:{THEME['accent']}; padding:5px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap; display:flex; align-items:center; gap:5px;">📅 Visitors today</div>
            <div onclick="window.sendChatAction('Who is meetings?')" style="background:white; border:1px solid {THEME['accent']}; color:{THEME['accent']}; padding:5px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap; display:flex; align-items:center; gap:5px;">👤 Host meeting</div>
            <div onclick="window.sendChatAction('last 30 days report')" style="background:white; border:1px solid {THEME['accent']}; color:{THEME['accent']}; padding:5px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap; display:flex; align-items:center; gap:5px;">📊 30D Report</div>
            <div onclick="window.sendChatAction('peak hours')" style="background:white; border:1px solid {THEME['accent']}; color:{THEME['accent']}; padding:5px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap; display:flex; align-items:center; gap:5px;">🕒 Peak analysis</div>
            <div onclick="window.sendChatAction('purpose stats')" style="background:white; border:1px solid {THEME['accent']}; color:{THEME['accent']}; padding:5px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap; display:flex; align-items:center; gap:5px;">🎯 Why they visit?</div>
            <div onclick="window.sendChatAction('feedback')" style="background:white; border:1px solid {THEME['accent']}; color:{THEME['accent']}; padding:5px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap; display:flex; align-items:center; gap:5px;">🌟 Give Feedback</div>
        </div>
        """
        
        return {
            "text": self.card("Universal Portal", body, "🏢", THEME['primary'], f"System Time: {datetime.now().strftime('%H:%M %p')}"),
            "actions": [
                {"text": "🚀 Full Dashboard", "url": url_for("main.index")},
                {"text": "🚨 Emergency", "action": "security"}
            ]
        }

    def ui_security_alert(self):
        html = f"""
        <div style="background:#fef2f2; border:2px solid {THEME['danger']}; border-radius:8px; padding:16px; text-align:center;">
            <div style="font-size:32px;">🚨</div>
            <div style="font-weight:900; color:{THEME['danger']}; font-size:16px; margin:8px 0;">SECURITY ALERT MODE</div>
            <div style="color:#991b1b; font-size:12px;">Initiating emergency protocols. Please confirm action.</div>
        </div>
        """
        return {
            "text": html,
            "actions": [{"text": "� Call Security", "action": "call_sec"}, {"text": "🔥 Evacuation List", "action": "evac_list"}]
        }

    def ui_polite_response(self):
        responses = ["You're very welcome.", "Happy to help.", "At your service.", "Anytime."]
        return {"text": f"😊 <strong>{random.choice(responses)}</strong>"}

    def ui_notify_prompt(self):
        session['chat_context'] = {'state': 'awaiting_host_notify'}
        return {"text": "📨 <strong>Host Notification</strong><br>Who do you need to send a message to?"}

    def ui_fallback(self):
        body = f"""
        <div style="text-align:center; padding:5px;">
            <div style="font-size:24px; margin-bottom:10px;">🤔</div>
            <div style="font-weight:bold; margin-bottom:5px;">I'm not sure about that.</div>
            <div style="font-size:11px; color:{THEME['text_sub']}; margin-bottom:15px;">Try one of the quick actions or example queries below.</div>
            
            <div style="display:flex; gap:6px; overflow-x:auto; padding-bottom:8px; margin-bottom:10px;">
                <div onclick="window.sendChatAction('stats')" style="background:{THEME['bg']}; border:1px solid {THEME['border']}; padding:6px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap;">📊 Overall Stats</div>
                <div onclick="window.sendChatAction('help')" style="background:{THEME['bg']}; border:1px solid {THEME['border']}; padding:6px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap;">🏠 Main Menu</div>
                <div onclick="window.sendChatAction('report')" style="background:{THEME['bg']}; border:1px solid {THEME['border']}; padding:6px 12px; border-radius:20px; font-size:11px; cursor:pointer; white-space:nowrap;">📁 Reports</div>
            </div>

            <div style="text-align:left; font-size:10px; color:{THEME['text_sub']}; font-weight:bold; margin-bottom:5px;">EXAMPLES:</div>
            <div style="text-align:left; font-size:11px; line-height:1.8;">
                • "Visitors from <strong>Google</strong>"<br>
                • "Who is meetings <strong>John</strong>?"<br>
                • "Show <strong>peak hours</strong> analysis"<br>
                • "Report for <strong>last 7 days</strong>"
            </div>
        </div>
        """
        return {
            "text": self.card("Support Hub", body, "🛰️", THEME['accent']),
            "actions": [{"text": "🚀 Open Dashboard", "url": url_for('main.index')}]
        }

    # --- 🛠️ FUNCTIONAL ACTIONS ---

    def action_dashboard(self):
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        # Stats
        cursor.execute("SELECT COUNT(*) as c FROM visitors WHERE status='IN'")
        active = cursor.fetchone()['c']
        
        cursor.execute("SELECT COUNT(*) as c FROM visitors")
        total_visitors = cursor.fetchone()['c']
        
        # Use Python date for consistency
        today_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) as c FROM visitors WHERE DATE(check_in)=%s", (today_date,))
        today = cursor.fetchone()['c']
        
        # New Advanced Stats
        cursor.execute("SELECT company, COUNT(*) as c FROM visitors GROUP BY company ORDER BY c DESC LIMIT 1")
        top_comp = cursor.fetchone()
        top_company = f"{top_comp['company']}" if top_comp else "N/A"
        
        cursor.execute("SELECT AVG(TIMESTAMPDIFF(MINUTE, check_in, check_out)) as avg_min FROM visitors WHERE status='OUT' AND check_out IS NOT NULL")
        res_avg = cursor.fetchone()
        if res_avg and res_avg['avg_min']:
             avg_dur = f"{round(res_avg['avg_min'])}m"
        else:
             avg_dur = "0m"
        
        # Micro-Chart
        chart_html = f'<div style="display:flex; align-items:flex-end; height:40px; gap:4px; margin-top:12px;">'
        max_v = 1
        # Optimized daily stats in ONE query
        cursor.execute("""
            SELECT DATE(check_in) as d, COUNT(*) as c 
            FROM visitors 
            WHERE check_in >= DATE(NOW()) - INTERVAL 4 DAY 
            GROUP BY d 
            ORDER BY d ASC
        """)
        day_results = {row['d'].strftime('%Y-%m-%d') if row['d'] else 'N/A': row['c'] for row in cursor.fetchall()}
        
        days_data = []
        for i in range(4, -1, -1):
            d_str = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            v = day_results.get(d_str, 0)
            days_data.append(v)
            if v > max_v: max_v = v
            
        for v in days_data:
            h = int((v / max_v) * 100) if max_v > 0 else 0
            chart_html += f'<div style="flex:1; background:{THEME["accent"]}; height:{max(10, h)}%; border-radius:2px; opacity:0.8;"></div>'
        chart_html += '</div>'
        
        body = f"""
        <div style="display:flex; justify-content:space-between; text-align:center; margin-bottom:12px; gap:8px;">
             <div style="flex:1; background:#f8fafc; padding:8px; border-radius:6px; border:1px solid #e2e8f0;">
                <div style="font-size:18px; font-weight:800; color:{THEME['accent']};">{active}</div>
                <div style="font-size:8px; color:{THEME['text_sub']}; font-weight:bold;">ACTIVE</div>
             </div>
             <div style="flex:1; background:#f8fafc; padding:8px; border-radius:6px; border:1px solid #e2e8f0;">
                <div style="font-size:18px; font-weight:800; color:{THEME['text_main']};">{today}</div>
                <div style="font-size:8px; color:{THEME['text_sub']}; font-weight:bold;">TODAY</div>
             </div>
             <div style="flex:1; background:#f8fafc; padding:8px; border-radius:6px; border:1px solid #e2e8f0;">
                <div style="font-size:18px; font-weight:800; color:{THEME['success']};">{total_visitors}</div>
                <div style="font-size:8px; color:{THEME['text_sub']}; font-weight:bold;">TOTAL LIFE</div>
             </div>
        </div>
        
        <div style="display:flex; justify-content:space-between; font-size:10px; color:{THEME['text_sub']}; background:{THEME['bg']}; padding:6px; border-radius:4px; margin-bottom:8px;">
            <span>🏢 Top: <strong>{top_company}</strong></span>
            <span>⏱️ Avg: <strong>{avg_dur}</strong></span>
        </div>
        
        {chart_html}
        """
        conn.close()
        return {"text": self.card("Live Analytics", body, "📈", THEME['primary'], "Last 5 Days Activity")}

    def action_notify_host(self, host_name):
        # Simulation of notification
        return {"text": f"✅ Notification sent to <strong>{host_name}</strong>.<br><small>They have been alerted of your inquiry.</small>"}

    def action_search(self, term):
        if not term:
            session['chat_context'] = {'state': 'awaiting_search'}
            return {"text": "🔎 <strong>Search:</strong> Who are you looking for?"}
            
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Multi-word robust search: Try full phrase first
        wild = f"%{term}%"
        cursor.execute("""
            SELECT id, visitor_name, company, status, purpose FROM visitors 
            WHERE visitor_name LIKE %s OR company LIKE %s OR vehicle_number LIKE %s OR purpose LIKE %s
            ORDER BY check_in DESC LIMIT 5
        """, (wild, wild, wild, wild))
        results = cursor.fetchall()
        
        if not results:
            # Fallback to individual word search
            words = term.split()
            for word in words:
                if len(word) < 2: continue
                w_wild = f"%{word}%"
                cursor.execute("""
                    SELECT id, visitor_name, company, status, purpose FROM visitors 
                    WHERE visitor_name LIKE %s OR company LIKE %s OR purpose LIKE %s
                    ORDER BY check_in DESC LIMIT 5
                """, (w_wild, w_wild, w_wild))
                results = cursor.fetchall()
                if results:
                    break

        conn.close()
        
        if not results:
            body = f"""
            <div style="text-align:center; padding:10px;">
                <div style="font-size:32px; margin-bottom:10px;">🔍</div>
                <div style="font-weight:bold;">No Matches Found</div>
                <div style="font-size:12px; color:{THEME['text_sub']}; margin-top:5px;">
                    We couldn't find any visitors matching '<strong>{term}</strong>'.
                </div>
            </div>
            """
            return {
                "text": self.card("Search", body, "❌", THEME['danger']),
                "actions": [{"text": "📊 All Visitors", "url": url_for('main.logs')}]
            }
        
        html = f"<div style='margin-bottom:10px; font-weight:bold; font-size:13px;'>Found {len(results)} matches for '{term}':</div>"
        for r in results:
            active = r['status'] == 'IN'
            status_color = THEME['success'] if active else THEME['text_sub']
            link = url_for("main.badge", id=r['id'])
            
            html += f"""
            <div style="margin-top:8px; padding:10px; background:{THEME['bg']}; border-radius:8px; border-left:4px solid {status_color};">
                <div style="display:flex; justify-content:space-between; align-items:start;">
                    <div>
                        <div style="font-weight:bold; font-size:12px; color:{THEME['text_main']};">{r['visitor_name']}</div>
                        <div style="font-size:10px; color:{THEME['text_sub']};">{r['company']} • {r['purpose']}</div>
                    </div>
                    <div style="font-size:8px; background:white; padding:2px 6px; border-radius:4px; border:1px solid #ddd;">{r['status']}</div>
                </div>
                <div style="text-align:right; margin-top:6px;">
                    <a href="{link}" style="font-size:10px; color:{THEME['accent']}; text-decoration:none; font-weight:bold;">VIEW PROFILE &rarr;</a>
                </div>
            </div>
            """
        return {
            "text": self.card("Search Results", html, "🔎", THEME['primary']),
            "actions": [{"text": "📋 Full Visitor Log", "url": url_for('main.logs')}]
        }

    def action_checkout(self, term):
        if not term:
             session['chat_context'] = {'state': 'awaiting_search'} # Re-use search flow for name
             return {"text": "🚪 <strong>Checkout:</strong> Who is leaving?"}
             
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        wild = f"%{term}%"
        cursor.execute("SELECT id, visitor_name FROM visitors WHERE status='IN' AND visitor_name LIKE %s LIMIT 3", (wild,))
        results = cursor.fetchall()
        conn.close()
        
        if not results: return {"text": "⚠️ No active visitor found."}
        
        html = "<div style='margin-bottom:10px; font-weight:bold; font-size:13px;'>Confirm Departure:</div>"
        for r in results:
            url = url_for("main.badge", id=r['id'])
            html += f"""
            <div style="margin-top:8px; padding:12px; background:{THEME['bg']}; border-radius:8px; border-left:4px solid {THEME['danger']};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-weight:bold; font-size:13px; color:{THEME['text_main']};">{r['visitor_name']}</div>
                        <div style="font-size:10px; color:{THEME['text_sub']};">Active Session</div>
                    </div>
                    <a href="{url}" style="background:{THEME['danger']}; color:white; font-size:11px; padding:6px 16px; border-radius:100px; text-decoration:none; font-weight:bold; letter-spacing:0.5px;">CHECKOUT</a>
                </div>
            </div>
            """
        return {"text": self.card("Departure Hub", html, "🚪", THEME['warning'])}

    def action_add_visitor(self, term=None):
        body = f"Ready to register '{term.title()}'?" if term else "Ready to register a new guest?"
        body += " Click the button below to open the registration form."
        return {
            "text": self.card("New Entry", body, "📝", THEME['success']),
            "actions": [{"text": "Open Registration Form", "url": url_for('main.add_visitor', visitor_name=term)}]
        }

    def action_export(self):
        m = self.message.lower()
        days = None
        label = "Current Data Overview"
        
        # Try dynamic days detection
        day_match = re.search(r'last (\d+) days', m)
        if day_match:
            days = int(day_match.group(1))
            label = f"Last {days} Days Analysis"
        elif 'last 90 days' in m: days = 90; label = "Last 90 Days Analysis"
        elif 'last 30 days' in m or 'last month' in m: days = 30; label = "Last 30 Days Analysis"
        elif 'last 7 days' in m or 'last week' in m: days = 7; label = "Last 7 Days Analysis"
        elif 'yesterday' in m: days = 1; label = "Yesterday's Analysis"
        elif 'today' in m: days = 0; label = "Today's Analysis"

        # If pure 'report' command without days, show the menu
        if days is None and ('report' in m or 'export' in m) and len(m.split()) < 3:
            return self.ui_reporting_menu()
        
        # 1. Fetch Stats for the Period
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Calculate Date SQL
        date_sql = ""
        if days == 0: date_sql = " AND DATE(check_in) = CURDATE()"
        elif days == 1: date_sql = " AND DATE(check_in) = SUBDATE(CURDATE(), 1)"
        elif days: date_sql = f" AND check_in >= DATE(NOW()) - INTERVAL {days} DAY"
        
        cursor.execute(f"SELECT COUNT(*) as c FROM visitors WHERE 1=1 {date_sql}")
        total = cursor.fetchone()['c']
        
        # Trends (Last 5 units of the period)
        chart_html = '<div style="display:flex; align-items:flex-end; height:30px; gap:4px; margin-top:10px;">'
        max_v = 1
        vals = []
        for i in range(4, -1, -1):
            if days is not None and days > 0:
                 # Sub-segments of the period
                 seg = max(1, days // 5)
                 d_start = datetime.now() - timedelta(days=(i+1)*seg)
                 d_end = datetime.now() - timedelta(days=i*seg)
                 cursor.execute("SELECT COUNT(*) as c FROM visitors WHERE check_in BETWEEN %s AND %s", (d_start, d_end))
            else:
                 # Default to daily
                 d = datetime.now() - timedelta(days=i)
                 cursor.execute("SELECT COUNT(*) as c FROM visitors WHERE DATE(check_in) = %s", (d.strftime('%Y-%m-%d'),))
            
            v = cursor.fetchone()['c']
            vals.append(v)
            if v > max_v: max_v = v
            
        for v in vals:
            h = int((v / max_v) * 100) if max_v > 0 else 0
            chart_html += f'<div style="flex:1; background:{THEME["accent"]}; height:{max(10, h)}%; border-radius:2px; opacity:0.8;"></div>'
        chart_html += '</div>'
        
        conn.close()

        body = f"""
        <div style="padding:4px;">
            <div style="background:{THEME['bg']}; padding:12px; border-radius:8px; border:1px solid {THEME['border']}; text-align:center; margin-bottom:15px;">
                <div style="font-size:32px; font-weight:900; color:{THEME['primary']};">{total}</div>
                <div style="font-size:10px; color:{THEME['text_sub']}; font-weight:bold; text-transform:uppercase;">TOTAL VISITORS</div>
            </div>
            
            <div style="font-size:11px; color:{THEME['text_main']}; margin-bottom:10px;">
                📈 <strong>Trend:</strong> Comparative performance for {label.lower()}
            </div>
            
            {chart_html}
            <div style="font-size:9px; text-align:center; color:{THEME['text_sub']}; margin-top:6px; font-weight:bold; letter-spacing:1px;">PERIOD ACTIVITY VOLUME</div>
        </div>
        """
        
        return {
            "text": self.card(label, body, "�", THEME['warning']),
            "actions": [
                {"text": "📋 View List", "event": "drillDown", "payload": {"days": days}},
                {"text": "📂 Download CSV", "url": url_for('main.export_csv', days=days)}
            ]
        }

    def ui_reporting_menu(self):
        body = """
        Select a period or ask for a custom range (e.g. "last 15 days report").<br><br>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
            <div onclick="window.sendChatAction('today report')" style="background:#fff7ed; border:1px solid #ffedd5; padding:12px 8px; border-radius:8px; text-align:center; cursor:pointer; font-weight:bold; color:#9a3412; font-size:13px;">📅 Today</div>
            <div onclick="window.sendChatAction('last 7 days report')" style="background:#fff7ed; border:1px solid #ffedd5; padding:12px 8px; border-radius:8px; text-align:center; cursor:pointer; font-weight:bold; color:#9a3412; font-size:13px;">📊 7 Days</div>
            <div onclick="window.sendChatAction('last 30 days report')" style="background:#fff7ed; border:1px solid #ffedd5; padding:12px 8px; border-radius:8px; text-align:center; cursor:pointer; font-weight:bold; color:#9a3412; font-size:13px;">🗓️ 30 Days</div>
            <div onclick="window.sendChatAction('last 90 days report')" style="background:#fff7ed; border:1px solid #ffedd5; padding:12px 8px; border-radius:8px; text-align:center; cursor:pointer; font-weight:bold; color:#9a3412; font-size:13px;">📈 90 Days</div>
        </div>
        """
        return {
            "text": self.card("Report Center", body, "📁", THEME['warning']),
            "actions": [{"text": "Download Full History", "url": url_for("main.export_csv")}]
        }

    def action_latest_logs(self):
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, visitor_name, company, status, purpose, check_in FROM visitors ORDER BY check_in DESC LIMIT 5")
        logs = cursor.fetchall()
        conn.close()
        
        if not logs: return {"text": "📭 No recent logs found."}
        
        html = "<div style='padding:2px;'>"
        for l in logs:
            is_active = l['status'] == 'IN'
            status_color = THEME['success'] if is_active else "#cbd5e1"
            status_text = "CHECKED IN" if is_active else "CHECKED OUT"
            relative_time = "Just now" # Simple simulation
            check_in_time = l['check_in'].strftime('%I:%M %p')
            
            html += f"""
            <div style="margin-bottom:12px; position:relative; padding-left:15px; border-left:2px solid {status_color};">
                <div style="font-size:12px; font-weight:700; color:{THEME['text_main']};">{l['visitor_name']}</div>
                <div style="font-size:10px; color:{THEME['text_sub']};">{l['company']} • {l['purpose']}</div>
                <div style="display:flex; justify-content:space-between; margin-top:4px;">
                    <span style="font-size:9px; font-weight:bold; color:{status_color};">{status_text}</span>
                    <span style="font-size:9px; color:{THEME['text_sub']}; font-family:monospace;">{check_in_time}</span>
                </div>
            </div>
            """
        html += "</div>"
        
        return {
            "text": self.card("Real-time Activity", html, "📡", THEME['primary']),
            "actions": [{"text": "📋 Full Visitor Log", "url": url_for('main.logs')}]
        }

    def action_search_host(self, host_name):
        if not host_name or len(host_name) < 2: 
             return {"text": "Please provide a valid host name (e.g. 'John')."}
             
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        wild = f"%{host_name}%"
        cursor.execute("SELECT id, visitor_name, company, status, check_in FROM visitors WHERE person_to_meet LIKE %s ORDER BY check_in DESC LIMIT 5", (wild,))
        results = cursor.fetchall()
        
        cursor.execute("SELECT COUNT(*) as c FROM visitors WHERE person_to_meet LIKE %s", (wild,))
        total_v = cursor.fetchone()['c']
        
        conn.close()
        
        if not results: return {"text": f"No recent visitors found for host matching '<strong>{host_name}</strong>'."}
        
        body = f"""
        <div style="margin-bottom:10px;">
            <div style="background:{THEME['bg']}; padding:8px; border-radius:6px; border:1px solid {THEME['border']}; text-align:center; margin-bottom:12px;">
                <div style="font-size:20px; font-weight:800; color:{THEME['accent']};">{total_v}</div>
                <div style="font-size:9px; color:{THEME['text_sub']}; font-weight:bold; text-transform:uppercase;">TOTAL LIFETIME VISITORS</div>
            </div>
        """
        for r in results:
             status_icon = "🟢" if r['status'] == 'IN' else "⚪"
             body += f"""
             <div style="font-size:11px; margin-bottom:6px; background:white; padding:6px; border-radius:4px; border:1px solid #f1f5f9; display:flex; justify-content:space-between;">
                 <span>{status_icon} {r['visitor_name']}</span>
                 <span style="color:{THEME['text_sub']}; font-size:9px;">{r['check_in'].strftime('%d %b')}</span>
             </div>
             """
        body += "</div>"
        
        return {
            "text": self.card(f"Host: {host_name.title()}", body, "👤", THEME['accent']),
            "actions": [
                {"text": "� View History", "event": "drillDown", "payload": {"search": host_name}},
                {"text": "📂 Export CSV", "url": url_for('main.export_csv', search=host_name)}
            ]
        }

    def action_weather(self):
        now = datetime.now()
        date_str = now.strftime("%A, %d %B %Y")
        time_str = now.strftime("%I:%M %p")
        
        # Proactive Logic
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as c FROM visitors WHERE status='IN'")
        active = cursor.fetchone()['c']
        conn.close()

        reminder = "System is stable."
        if now.hour > 17: reminder = "Evening protocols active. Check for stay-overs."
        elif active > 10: reminder = f"High occupancy detected ({active} active). Monitor traffic."
        elif now.hour < 9: reminder = "Welcome! System initialized for the day."

        # Weather simulation
        temp = random.randint(22, 28)
        cond = random.choice(["Sunny", "Partly Cloudy", "Clear Skies"])
        icon = "☀️" if now.hour < 18 else "🌙"

        body = f"""
        <div style="text-align:center; padding:10px;">
             <div style="font-size:28px; font-weight:800; color:{THEME['primary']}; letter-spacing:-1px;">{time_str}</div>
             <div style="font-size:11px; color:{THEME['text_sub']}; text-transform:uppercase; margin-bottom:15px; font-weight:bold;">{date_str}</div>
             
             <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:15px;">
                <div style="background:#f0f9ff; padding:8px; border-radius:6px; border:1px solid #bae6fd;">
                    <div style="font-size:10px; color:#0369a1; font-weight:bold;">{icon} WEATHER</div>
                    <div style="font-size:12px; font-weight:bold;">{temp}°C {cond}</div>
                </div>
                <div style="background:#f0fdf4; padding:8px; border-radius:6px; border:1px solid #bbf7d0;">
                    <div style="font-size:10px; color:#15803d; font-weight:bold;">NETWORK</div>
                    <div style="font-size:12px; font-weight:bold;">Online ✅</div>
                </div>
             </div>

             <div style="background:{THEME['bg']}; color:{THEME['accent']}; font-size:11px; padding:10px; border-radius:8px; font-weight:600; border:1px solid {THEME['border']}; border-left:4px solid {THEME['accent']};">
                💡 {reminder}
             </div>
        </div>
        """
        return {"text": self.card("System Clock", body, icon, THEME['accent'])}

    def action_generate_qr(self, term):
        if not term: return {"text": "Please provide a name or ID to generate a pass (e.g., 'QR for John')."}
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        if term.isdigit():
             sql = "SELECT id, visitor_name, company, status, purpose FROM visitors WHERE id = %s"
        else:
             sql = "SELECT id, visitor_name, company, status, purpose FROM visitors WHERE visitor_name LIKE %s LIMIT 1"
             term = f"%{term}%"
             
        cursor.execute(sql, (term,))
        v = cursor.fetchone()
        conn.close()
        
        if not v:
            return {"text": f"❌ No matching visitor found for '<strong>{term}</strong>'. Try a different name."}
        
        qr_data = url_for('main.badge', id=v['id'], _external=True)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_data}"
        
        body = f"""
        <div style="text-align:center; padding:5px;">
            <div style="background:white; padding:15px; border-radius:12px; border:1px solid {THEME['border']}; margin-bottom:12px;">
                <img src="{qr_url}" style="width:140px; height:140px; border:4px solid white; border-radius:8px;">
                <div style="margin-top:10px;">
                    <div style="font-weight:900; font-size:16px; color:{THEME['primary']};">{v['visitor_name']}</div>
                    <div style="font-size:11px; color:{THEME['text_sub']}; text-transform:uppercase; font-weight:bold;">{v['company']}</div>
                </div>
            </div>
            
            <div style="background:#f1f5f9; padding:8px; border-radius:6px; font-size:10px; color:{THEME['text_sub']}; display:flex; justify-content:space-between; margin-bottom:10px;">
                <span>STATUS: <strong>{v['status']}</strong></span>
                <span>ID: <strong>#{v['id']}</strong></span>
            </div>
            
            <a href="{url_for('main.badge', id=v['id'])}" style="display:block; background:{THEME['primary']}; color:white; padding:8px; border-radius:6px; text-decoration:none; font-size:12px; font-weight:bold;">📄 VIEW FULL BADGE</a>
        </div>
        """
        return {
            "text": self.card("Digital Access Pass", body, "🎟️", THEME['primary']),
            "actions": [{"text": "🖨️ Print Badge", "url": url_for('main.badge', id=v['id'])}]
        }

    def action_room_status(self):
        rooms = [
            {"name": "Boardroom A", "status": "Available", "color": "#10b981"},
            {"name": "Conference Hall", "status": "Occupied (until 4 PM)", "color": "#ef4444"},
            {"name": "Meeting Room 1", "status": "Available", "color": "#10b981"},
            {"name": "Focus Pod", "status": "Cleaning", "color": "#f59e0b"}
        ]
        
        html = "<strong>Meeting Room Status:</strong><div style='margin-top:8px;'>"
        for r in rooms:
            html += f"""
            <div style="display:flex; justify-content:space-between; margin-bottom:6px; font-size:11px; background:#fff; padding:6px; border-radius:4px; border-left:3px solid {r['color']}; box-shadow:0 1px 2px rgba(0,0,0,0.05);">
                <span style="font-weight:600;">{r['name']}</span>
                <span style="color:{r['color']}; font-weight:700;">{r['status']}</span>
            </div>
            """
        html += "</div>"
        return {"text": self.card("Room Availability", html, "🏢", THEME['accent'])}

    def action_vip_protocol(self):
        body = f"""
        <div style="background:#fff7ed; padding:12px; border-radius:6px; border-left:4px solid {THEME['warning']};">
            <strong style="color:#c2410c; display:block; margin-bottom:8px;">⚠️ VIP PROTOCOL ACTIVATED</strong>
            <ul style="margin:0; padding-left:20px; font-size:12px; color:#9a3412;">
                <li>Notify Senior Management</li>
                <li>Clear elevator C for priority use</li>
                <li>Prepare Executive Lounge</li>
                <li>Assign Security Escort (Team Alpha)</li>
            </ul>
        </div>
        """
        return {
            "text": self.card("VIP Alert", body, "👑", THEME['warning'], "High Priority Mode Active"),
            "actions": [{"text": "📞 Call Director", "url": "tel:123"}, {"text": "🛑 Security Alert", "action": "call_sec"}]
        }

    def action_language_greeting(self):
        m = self.message
        greeting = "Hello"
        if "hola" in m: greeting = "¡Hola! Bienvenido."
        elif "bonjour" in m: greeting = "Bonjour! Bienvenue."
        elif "namaste" in m: greeting = "Namaste! Swagat he."
        elif "ciao" in m: greeting = "Ciao! Benvenuto."
        elif "hallo" in m or "guten" in m: greeting = "Hallo! Willkommen."
        
        return self.ui_greeting(f"🌍 <strong>{greeting}</strong><br>I speak many languages, but I work best in English.")

    def action_shed_status(self):
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM sheds")
        sheds = cursor.fetchall()
        
        html = '<div style="display:grid; grid-template-columns:1fr; gap:8px;">'
        for s in sheds:
            status_color = THEME['success'] if s['status'] == 'AVAILABLE' else THEME['danger'] if s['status'] == 'OCCUPIED' else THEME['text_sub']
            icon = "📦" if s['status'] == 'OCCUPIED' else "✅"
            customer = f'<div style="font-size:10px; color:{THEME["text_sub"]};">Client: {s["customer_name"]}</div>' if s['customer_name'] else ''
            
            html += f"""
            <div style="background:{THEME['bg']}; padding:10px; border-radius:8px; border:1px solid {THEME['border']}; border-left:4px solid {status_color};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-weight:bold;">{icon} {s['name']}</div>
                    <div style="font-size:9px; color:{status_color}; font-weight:800;">{s['status']}</div>
                </div>
                {customer}
            </div>
            """
        html += '</div>'
        return {
            "text": self.card("Shed Monitoring", html, "🏭", THEME['primary']),
            "actions": [{"text": "🚀 Open Logistics Hub", "url": url_for("main.logistics")}]
        }

    def action_room_management(self):
        m = self.message
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Handle "block" command if room name is present
        if "block" in m or "lock" in m:
            # Simple heuristic to find room name
            cursor.execute("SELECT id, name FROM meeting_rooms")
            rooms = cursor.fetchall()
            target_room = None
            for r in rooms:
                if r['name'].lower() in m:
                    target_room = r
                    break
            
            if target_room:
                cursor.execute("UPDATE meeting_rooms SET status='BLOCKED', blocked_reason='System Blocked' WHERE id=%s", (target_room['id'],))
                conn.commit()
                return {"text": f"✅ <strong>{target_room['name']}</strong> has been successfully blocked from further bookings."}

        cursor.execute("SELECT * FROM meeting_rooms")
        rooms = cursor.fetchall()
        
        html = '<div style="display:grid; grid-template-columns:1fr; gap:8px;">'
        actions = []
        for r in rooms:
            status_color = {
                'AVAILABLE': THEME['success'],
                'OCCUPIED': THEME['danger'],
                'BLOCKED': THEME['text_main'],
                'CLEANING': THEME['warning']
            }.get(r['status'], THEME['text_sub'])
            
            html += f"""
            <div style="background:{THEME['bg']}; padding:10px; border-radius:8px; border:1px solid {THEME['border']}; border-left:4px solid {status_color};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="font-weight:bold;">🏢 {r['name']}</div>
                    <div style="font-size:9px; color:{status_color}; font-weight:800;">{r['status']}</div>
                </div>
                {f'<div style="font-size:9px; color:red;">Reason: {r["blocked_reason"]}</div>' if r['status'] == 'BLOCKED' else ''}
            </div>
            """
            if r['status'] == 'AVAILABLE':
                actions.append({"text": f"Block {r['name']}", "action": f"block {r['name']}"})

        html += '</div>'
        return {
            "text": self.card("Room Management", html, "🏢", THEME['accent']),
            "actions": actions[:2] + [{"text": "🚀 Logistics Hub", "url": url_for("main.logistics")}]
        }

    def action_broadcast(self, msg):
        if not msg: return {"text": "What message would you like to announce?"}
        
        # Simulated broadcast logic
        body = f"""
        <div style="text-align:center; padding:10px;">
            <div style="font-size:32px;">📢</div>
            <div style="font-weight:bold; margin:8px 0;">Broadcasting System</div>
            <div style="font-style:italic; color:{THEME['text_sub']};">"{msg}"</div>
            <div style="margin-top:10px; font-size:10px; color:{THEME['success']};">✅ Sent to all active screens</div>
        </div>
        """
        return {"text": self.card("Announcement", body, "📡", THEME['warning'])}

    def action_specific_stats(self, term):
        if not term: return self.action_dashboard()
        m = self.message
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        wild = f"%{term}%"
        
        # Helper to get trend
        def get_trend(f_sql, f_params):
            d1 = datetime.now() - timedelta(days=30)
            cursor.execute(f"SELECT COUNT(*) as c FROM visitors WHERE check_in > %s AND {f_sql}", (d1, *f_params))
            return cursor.fetchone()['c']

        # 1. Capture Date/Status Overrides from Message
        days_override = None
        status_override = None
        date_filter_sql = ""
        date_params = []
        date_label = "Total (All Time)"
        
        # Dynamic Days
        day_match = re.search(r'last (\d+) days', m)
        if day_match:
            days_override = int(day_match.group(1))
            date_filter_sql = f" AND check_in >= DATE(NOW()) - INTERVAL {days_override} DAY"
            date_label = f"Total (Last {days_override} Days)"
        elif 'today' in m:
            days_override = 0
            date_filter_sql = " AND DATE(check_in) = CURDATE()"
            date_label = "Total (Today)"
        elif 'yesterday' in m:
            days_override = 1
            date_filter_sql = " AND DATE(check_in) = SUBDATE(CURDATE(), 1)"
            date_label = "Total (Yesterday)"
        elif 'last 7 days' in m or 'week' in m:
            days_override = 7
            date_filter_sql = " AND check_in >= DATE(NOW()) - INTERVAL 7 DAY"
            date_label = "Total (Last 7 Days)"
        elif 'last 30 days' in m or 'month' in m:
            days_override = 30
            date_filter_sql = " AND check_in >= DATE(NOW()) - INTERVAL 30 DAY"
            date_label = "Total (Last 30 Days)"

        if 'active' in m or 'inside' in m or 'on site' in m:
            status_override = 'IN'

        # 2. Match Target Logic
        match_type = None
        count = 0
        active_count = 0
        trend_30 = 0
        search_target = term
        
        targets = [
            ("Company", "company"),
            ("Purpose", "purpose"),
            ("Visitor", "visitor_name"),
            ("Host", "person_to_meet")
        ]
        
        final_filter = "1=1"
        final_params = []

        is_status_only = term in ['active', 'in', 'inside', 'on site']
        if is_status_only:
            match_type = "Active visitors"
            final_filter = "status='IN'"
            search_target = ""
        else:
            # Multi-word robust search: try each word individually
            words = term.split()
            found = False
            for word in words:
                if len(word) < 2: continue
                w_wild = f"%{word}%"
                for label, column in targets:
                    cursor.execute(f"SELECT COUNT(*) as c FROM visitors WHERE {column} LIKE %s {date_filter_sql}", (w_wild, *date_params))
                    if cursor.fetchone()['c'] > 0:
                        match_type = f"{label}: {word.title()}"
                        final_filter = f"{column} LIKE %s"
                        final_params = [w_wild]
                        found = True
                        break
                if found: break
            
            # If no single word match, try the whole phrase as fallback
            if not found:
                for label, column in targets:
                    cursor.execute(f"SELECT COUNT(*) as c FROM visitors WHERE {column} LIKE %s {date_filter_sql}", (wild, *date_params))
                    if cursor.fetchone()['c'] > 0:
                        match_type = f"{label}: {term.title()}"
                        final_filter = f"{column} LIKE %s"
                        final_params = [wild]
                        break
        
        if not match_type:
            # If a term was provided but not matched, return professional No Results
            if term:
                body = f"""
                <div style="text-align:center; padding:10px;">
                    <div style="font-size:32px; margin-bottom:10px;">🔍</div>
                    <div style="font-weight:bold; color:{THEME['text_main']};">No Results Found</div>
                    <div style="font-size:12px; color:{THEME['text_sub']}; margin-top:5px;">
                        We couldn't find any records matching '<strong>{term}</strong>'. 
                        Try searching by Company, Visitor Name, or Host.
                    </div>
                </div>
                """
                return {
                    "text": self.card("Search Result", body, "❌", THEME['danger']),
                    "actions": [
                        {"text": "📊 Full Dashboard", "url": url_for('main.index')},
                        {"text": "📋 View Recent", "action": "latest_logs"}
                    ]
                }
            
            # Fallback for date-only queries (e.g. "visitors today")
            match_type = date_label.replace("Total (", "").replace(")", "") or "Visitors"
            final_filter = "1=1"
            search_target = ""

        # Now get the actual counts with proper intersections
        status_sql = " AND status='IN'" if status_override == 'IN' else ""
        sql_params = tuple(final_params) + tuple(date_params)
        cursor.execute(f"SELECT COUNT(*) as c FROM visitors WHERE {final_filter} {date_filter_sql} {status_sql}", sql_params)
        count = cursor.fetchone()['c']
        
        cursor.execute(f"SELECT COUNT(*) as c FROM visitors WHERE {final_filter} AND status='IN'", tuple(final_params))
        active_count = cursor.fetchone()['c']
        
        trend_30 = get_trend(final_filter, final_params)

        # 3. Generate Chart
        chart_html = '<div style="display:flex; align-items:flex-end; height:30px; gap:4px; margin-top:8px;">'
        max_v = 1
        vals = []
        for i in range(4, -1, -1):
            d = datetime.now() - timedelta(days=i)
            cursor.execute(f"SELECT COUNT(*) as c FROM visitors WHERE DATE(check_in)=%s AND {final_filter}", (d.strftime('%Y-%m-%d'),) + tuple(final_params))
            v = cursor.fetchone()['c']
            vals.append(v)
            if v > max_v: max_v = v
        for v in vals:
            h = int((v / max_v) * 100) if max_v > 0 else 0
            chart_html += f'<div style="flex:1; background:{THEME["accent"]}; height:{max(10, h)}%; border-radius:2px; opacity:0.8;"></div>'
        chart_html += '</div>'

        # 4. Contextual Actions
        drill_payload = {"search": "" if is_status_only else term, "status": status_override or "", "days": days_override}
        export_args = {"search": "" if is_status_only else term, "status": status_override or "", "days": days_override}
        
        actions = [
            {
                "text": f"📋 View {match_type} List", 
                "event": "drillDown", 
                "payload": drill_payload
            },
            {
                "text": "📂 Export Data", 
                "url": url_for('main.export_csv', **{k: v for k, v in export_args.items() if v is not None})
            }
        ]

        conn.close()

        body = f"""
        <div style="padding:4px;">
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:12px;">
                <div style="background:#f8fafc; padding:10px; border-radius:6px; border:1px solid #e2e8f0; text-align:center;">
                    <div style="font-size:24px; font-weight:800; color:{THEME['primary']};">{count}</div>
                    <div style="font-size:10px; color:{THEME['text_sub']}; text-transform:uppercase;">{date_label if not status_override else 'MATCHED'}</div>
                </div>
                <div style="background:#f8fafc; padding:10px; border-radius:6px; border:1px solid #e2e8f0; text-align:center;">
                    <div style="font-size:24px; font-weight:800; color:{THEME['accent']};">{active_count}</div>
                    <div style="font-size:10px; color:{THEME['text_sub']}; text-transform:uppercase;">CURRENT IN</div>
                </div>
            </div>
            
            <div style="display:flex; gap:6px; margin:10px 0; overflow-x:auto; padding-bottom:4px;">
                <div onclick="window.sendChatAction('active {term}')" style="background:{THEME['bg']}; padding:4px 10px; border-radius:15px; border:1px solid {THEME['border']}; font-size:10px; color:{THEME['text_sub']}; cursor:pointer; white-space:nowrap;">🟢 Active</div>
                <div onclick="window.sendChatAction('today {term}')" style="background:{THEME['bg']}; padding:4px 10px; border-radius:15px; border:1px solid {THEME['border']}; font-size:10px; color:{THEME['text_sub']}; cursor:pointer; white-space:nowrap;">📅 Today</div>
                <div onclick="window.sendChatAction('last 30 days {term}')" style="background:{THEME['bg']}; padding:4px 10px; border-radius:15px; border:1px solid {THEME['border']}; font-size:10px; color:{THEME['text_sub']}; cursor:pointer; white-space:nowrap;">🕒 30D Trend</div>
            </div>

            <div style="font-size:11px; color:#64748b; background:#f1f5f9; padding:8px; border-radius:6px; text-align:center; margin-bottom:10px; border-left:4px solid {THEME['accent']};">
                🚀 <strong>{trend_30}</strong> visits captured in last 30 days
            </div>
            {chart_html}
            <div style="font-size:9px; text-align:center; color:{THEME['text_sub']}; margin-top:6px; font-weight:bold; letter-spacing:1px;">DAILY PERFORMANCE (LAST 5 DAYS)</div>
        </div>
        """

        return {
            "text": self.card("Deep Analytics", body, "📊", THEME['primary']),
            "actions": actions
        }


    def action_knowledge_base(self):
        m = self.message
        answer = "I'm not sure about that specific detail."
        for k, v in KNOWLEDGE_BASE.items():
            if k in m:
                answer = v
                break
        return {"text": f"💡 <strong>Did you know?</strong><br>{answer}"}


    def action_insights(self):
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        m = self.message

        if 'busiest' in m or 'peak' in m or 'time' in m:
            # Peak Hours Analysis
            cursor.execute("""
                SELECT HOUR(check_in) as h, COUNT(*) as c 
                FROM visitors 
                GROUP BY h 
                ORDER BY c DESC 
                LIMIT 3
            """)
            peaks = cursor.fetchall()
            
            body = "<div style='padding:10px;'>"
            if peaks:
                top_h = peaks[0]['h']
                top_c = peaks[0]['c']
                ampm = datetime.strptime(str(top_h), "%H").strftime("%I %p")
                
                body += f"""
                <div style="text-align:center; margin-bottom:15px;">
                    <div style="font-size:32px;">🕒</div>
                    <div style="font-weight:bold; font-size:16px; color:{THEME['primary']};">Peak Traffic: {ampm}</div>
                    <div style="color:{THEME['text_sub']}; font-size:11px;">Approx. {top_c} visitors usually check-in around this time.</div>
                </div>
                <div style="background:#f8fafc; padding:8px; border-radius:6px;">
                    <div style="font-size:10px; font-weight:bold; color:{THEME['text_sub']}; margin-bottom:4px;">BUSIEST HOURS</div>
                """
                for p in peaks:
                    h_str = datetime.strptime(str(p['h']), "%H").strftime("%I %p")
                    pct = int((p['c'] / top_c) * 100)
                    body += f"""
                    <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px; font-size:11px;">
                        <span style="width:40px;">{h_str}</span>
                        <div style="flex:1; background:#e2e8f0; height:6px; border-radius:3px;">
                            <div style="width:{pct}%; background:{THEME['accent']}; height:100%; border-radius:3px;"></div>
                        </div>
                        <span style="width:20px; text-align:right;">{p['c']}</span>
                    </div>
                    """
                body += "</div>"
            else:
                body += "Not enough data to determine peak hours."
            body += "</div>"
            
            conn.close()
            return {"text": self.card("Traffic Insights", body, "⚡", THEME['warning'])}

        elif 'top' in m or 'frequent' in m or 'frequent' in m or 'visitor' in m:
            # Top Visitors / Companies
            cursor.execute("""
                SELECT visitor_name, COUNT(*) as c 
                FROM visitors 
                GROUP BY visitor_name 
                ORDER BY c DESC 
                LIMIT 3
            """)
            top_visitors = cursor.fetchall()
            
            body = "<div style='padding:5px;'>"
            body += f"<div style='font-size:11px; color:{THEME['text_sub']}; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.5px;'>🏆 Most Frequent Visitors</div>"
            
            actions = []
            
            for i, v in enumerate(top_visitors):
                rank = ["🥇", "🥈", "🥉"][i] if i < 3 else f"#{i+1}"
                name = v['visitor_name']
                count = v['c']
                body += f"""
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; padding:8px; background:{THEME['bg']}; border-radius:6px; border:1px solid #f1f5f9;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-size:14px;">{rank}</span>
                        <span style="font-weight:600; font-size:13px; color:{THEME['text_main']};">{name}</span>
                    </div>
                    <span style="background:{THEME['primary']}; color:white; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:bold;">{count}</span>
                </div>
                """
                # Add drill-down action for the top visitor
                if i == 0:
                     actions.append({"text": f"📋 View {name}'s History", "event": "drillDownPurpose", "payload": name})

            body += "</div>"
            conn.close()
            
            return {
                "text": self.card("Top Visitors", body, "🌟"),
                "actions": actions
            }

        elif 'purpose' in m or 'why' in m:
            # Purpose Breakdown
            cursor.execute("SELECT purpose, COUNT(*) as c FROM visitors GROUP BY purpose ORDER BY c DESC LIMIT 4")
            reasons = cursor.fetchall()
            
            body = "<div style='padding:5px; font-size:11px;'>"
            body += f"<div style='margin-bottom:10px; color:{THEME['text_sub']}'>VISITATION REASONS BREAKDOWN</div>"
            
            total = sum(r['c'] for r in reasons)
            for r in reasons:
                pct = int((r['c'] / total) * 100) if total > 0 else 0
                body += f"""
                <div style="margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:2px;">
                        <strong>{r['purpose']}</strong>
                        <span>{pct}%</span>
                    </div>
                    <div style="background:#e2e8f0; height:4px; border-radius:2px;">
                        <div style="width:{pct}%; background:{THEME['accent']}; height:100%; border-radius:2px;"></div>
                    </div>
                </div>
                """
            body += "</div>"
            conn.close()
            return {"text": self.card("Purpose Analysis", body, "🎯", THEME['primary'])}

        elif 'weekly' in m or 'summary' in m:
            # Weekly Performance
            cursor.execute("SELECT COUNT(*) as c, DATE(check_in) as d FROM visitors WHERE check_in >= DATE(NOW()) - INTERVAL 7 DAY GROUP BY d ORDER BY d ASC")
            weekly = cursor.fetchall()
            avg_w = sum(w['c'] for w in weekly) / len(weekly) if weekly else 0
            
            body = f"""
            <div style="text-align:center; padding:5px;">
                <div style="font-size:24px; font-weight:800; color:{THEME['accent']};">{len(weekly)} Days</div>
                <div style="font-size:10px; color:{THEME['text_sub']}; text-transform:uppercase;">Weekly Analysis Active</div>
                <div style="background:{THEME['bg']}; padding:10px; border-radius:8px; margin-top:10px; border:1px solid {THEME['border']};">
                    Average Daily Traffic: <strong>{round(avg_w, 1)} visitors</strong>
                </div>
            </div>
            """
            conn.close()
            return {"text": self.card("Weekly Digest", body, "📅", THEME['success'])}

        elif 'feedback' in m:
            return {
                "text": "🌟 <strong>Help us improve!</strong><br>How would you rate your experience with the Visitor Assistant today?",
                "actions": [
                    {"text": "⭐⭐⭐⭐⭐ Excellent", "action": "thanks"},
                    {"text": "⭐⭐⭐ Good", "action": "thanks"},
                    {"text": "💬 Add Suggestion", "action": "notify"}
                ]
            }
        
        else:
             conn.close()
             return self.ui_greeting("I couldn't find a specific insight for that. Here are some options available:")

def process_message(message, user_id=None):
    bot = VisitorBot(message, user_id)
    return bot.respond()
