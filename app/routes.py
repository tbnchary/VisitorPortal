from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response, jsonify
from app.db import get_db, ensure_sidebar_menu
from app.chatbot_logic import process_message
from functools import wraps
from datetime import datetime, timedelta
import csv
import io
from openpyxl import Workbook
from flask import send_file

bp = Blueprint('main', __name__)

def ensure_visitor_form_settings():
    """Ensure visitor_form_settings table exists and is seeded with defaults"""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Ensure visitor_form_settings table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visitor_form_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            field_key VARCHAR(50) UNIQUE NOT NULL,
            field_label VARCHAR(100) NOT NULL,
            is_required BOOLEAN DEFAULT FALSE,
            is_visible BOOLEAN DEFAULT TRUE,
            section VARCHAR(50) DEFAULT 'General'
        )
    """)
    conn.commit()

    # Default fields to seed if table is empty
    default_fields = [
        ('visitor_name', 'Full Name', True, True, 'Visitor Info'),
        ('phone', 'Phone Number', True, True, 'Visitor Info'),
        ('email', 'Email Address', False, True, 'Visitor Info'),
        ('company', 'Company Name', False, True, 'Visitor Info'),
        ('purpose', 'Purpose of Visit', True, True, 'Visit Details'),
        ('person_to_meet', 'Host / Person to Meet', True, True, 'Visit Details'),
        ('expected_duration', 'Expected Duration', False, True, 'Visit Details'),
        ('visitor_type', 'Visitor Type', False, True, 'Visit Details'),
        ('vehicle_number', 'Vehicle Number', False, True, 'Security'),
        ('id_type', 'ID Type', False, True, 'Security'),
        ('laptop_serial', 'Laptop Serial (if any)', False, True, 'Security'),
        ('additional_visitors_count', 'Additional Visitors', False, True, 'Security'),
        ('signature', 'Digital Signature', True, True, 'Security'),
        ('photo', 'Identity Photo', True, True, 'Identification')
    ]

    cursor.execute("SELECT COUNT(*) as count FROM visitor_form_settings")
    if cursor.fetchone()['count'] == 0:
        cursor.executemany("""
            INSERT INTO visitor_form_settings (field_key, field_label, is_required, is_visible, section)
            VALUES (%s, %s, %s, %s, %s)
        """, default_fields)
        conn.commit()
    return cursor

def ensure_draft_column():
    """Ensure visitors table has is_draft column for draft functionality and robust status column"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. Check for draft columns
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'visitors' 
            AND COLUMN_NAME = 'is_draft'
        """)
        result = cursor.fetchone()
        if result[0] == 0:
            cursor.execute("ALTER TABLE visitors ADD COLUMN is_draft BOOLEAN DEFAULT FALSE AFTER health_declaration_clear")
            cursor.execute("ALTER TABLE visitors ADD COLUMN draft_created_by INT DEFAULT NULL AFTER is_draft")
            cursor.execute("ALTER TABLE visitors ADD COLUMN draft_created_at DATETIME DEFAULT NULL AFTER draft_created_by")
            cursor.execute("ALTER TABLE visitors ADD COLUMN draft_notes TEXT DEFAULT NULL AFTER draft_created_at")
            conn.commit()
            print("✅ Draft columns added to visitors table")

        # 2. Ensure status column is VARCHAR to prevent truncation errors with 'DRAFT' or other values
        cursor.execute("ALTER TABLE visitors MODIFY COLUMN status VARCHAR(20) DEFAULT 'IN'")
        
        # 3. Ensure check_in column in visitors table allows NULL (needed for drafts)
        cursor.execute("ALTER TABLE visitors MODIFY COLUMN check_in DATETIME NULL")
        
        conn.commit()
        print("✅ Status column and check_in constraints normalized")
        
    except Exception as e:
        print(f"Error ensuring draft/status columns: {e}")
    finally:
        cursor.close()

# --- LOGIN DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('main.login'))
            
        # Role-based protection: Prevent SECURITY from accessing random pages directly
        if session.get('role') == 'SECURITY':
            allowed_endpoints = [
                # Core pages Security can access
                'main.index', 'main.logs', 'main.add_visitor', 'main.view_visitor',
                'main.logout', 'main.profile', 'main.change_password',
                # Security dedicated dashboard
                'main.security_dashboard',
                # Visitor operations
                'main.checkout', 'main.manual_checkout', 'main.update_visitor_status',
                'main.badge', 'main.resend_badge', 'main.verify_visitor', 'main.self_checkout',
                'main.host_approvals', 'main.host_approve_visitor',
                'main.department_approvals',
                # Kiosk (public-facing but security can open it too)
                'main.kiosk', 'main.kiosk_register', 'main.kiosk_success',
                # Deletion workflow
                'main.request_deletion', 'main.approve_deletion', 'main.reject_deletion',
                # API endpoints needed by Security dashboard/pages
                'main.api_quick_visitors', 'main.api_get_sidebar_menu',
                'main.api_analytics_drilldown', 'main.api_visitor_details',
                'main.search_visitors_api', 'main.chart_data_api',
                'main.update_welcome_note', 'main.chat_message',
                'main.visitor_logistics', 'main.approve_visitor_logistics',
                'main.delete_draft', 'main.activate_draft', 'main.draft_list',
                'main.update_welcome_note', 'main.chat_message',
                'main.visitor_logistics', 'main.approve_visitor_logistics',
            ]
            if request.endpoint not in allowed_endpoints and not request.endpoint.startswith('static'):
                flash("Access Denied: You do not have permission to view that page.", "danger")
                return redirect(url_for('main.index'))
                
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        conn = get_db()
        try:
            cursor = conn.cursor(dictionary=True)
            # In production, use hashed passwords!
            cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
            user = cursor.fetchone()
            
            if user:
                # Check if user is approved
                if user.get('status') == 'PENDING':
                    flash("Your account is pending approval. Please wait for an administrator to approve your account.", "warning")
                elif user.get('status') == 'REJECTED':
                    flash("Your account has been rejected. Please contact the administrator.", "danger")
                elif user.get('status') == 'APPROVED':
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user.get('role', 'RECEPTION')
                    session['unit'] = user.get('unit', '')
                    # Role-based redirect on login
                    role_redirect = user.get('role', 'RECEPTION')
                    if role_redirect == 'SECURITY':
                        return redirect(url_for('main.security_dashboard'))
                    elif role_redirect in ['HOST', 'ADMIN']:
                        return redirect(url_for('main.inbox'))
                    return redirect(url_for('main.index'))
                else:
                    # Fallback for users without status
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user.get('role', 'RECEPTION')
                    session['unit'] = user.get('unit', '')
                    role_redirect = user.get('role', 'RECEPTION')
                    if role_redirect == 'SECURITY':
                        return redirect(url_for('main.security_dashboard'))
                    elif role_redirect in ['HOST', 'ADMIN']:
                        return redirect(url_for('main.inbox'))
                    return redirect(url_for('main.index'))
            else:
                flash("Invalid username or password.", "danger")
        finally:
            cursor.close()

    return render_template("login.html")
@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('main.login'))

@bp.route("/register", methods=["GET", "POST"])
def register():
    """User registration page"""
    if request.method == "POST":
        full_name = request.form.get("full_name")
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        role = request.form.get("role")
        unit = request.form.get("unit", "")
        
        phone = request.form.get("phone")
        
        # Validation
        if not all([full_name, username, email, password, confirm_password, role]):
            flash("All fields are required", "warning")
            return redirect(url_for('main.register'))
        
        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for('main.register'))
        
        if len(password) < 6:
            flash("Password must be at least 6 characters long", "warning")
            return redirect(url_for('main.register'))
        
        if len(username) < 3:
            flash("Username must be at least 3 characters long", "warning")
            return redirect(url_for('main.register'))
        
        if role not in ['ADMIN', 'RECEPTION', 'SECURITY']:
            flash("Invalid role selected", "danger")
            return redirect(url_for('main.register'))
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Check if username already exists
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash("Username already exists. Please choose a different username.", "danger")
                return redirect(url_for('main.register'))
            
            # Check if email already exists
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                flash("Email already registered. Please use a different email.", "danger")
                return redirect(url_for('main.register'))
            
            
            # Insert new user with PENDING status
            cursor.execute("""
                INSERT INTO users (full_name, username, email, phone, password, role, status, unit)
                VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', %s)
            """, (full_name, username, email, phone, password, role, unit))
            conn.commit()
            
            flash("Account created successfully! Your account is pending approval. An administrator will review your request shortly.", "success")
            return redirect(url_for('main.login'))
            
        except Exception as e:
            flash(f"Registration failed: {str(e)}", "danger")
            return redirect(url_for('main.register'))
        finally:
            cursor.close()
    
    return render_template("register.html")





@bp.route("/camera-test")
def camera_test():
    """Simple camera test page for debugging"""
    return render_template("camera_test.html")


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username_or_email = request.form.get("username")
        
        if not username_or_email:
            flash("Please enter your username or email.", "warning")
            return redirect(url_for('main.forgot_password'))
        
        # Check if user exists by username or email
        conn = get_db()
        try:
            cursor = conn.cursor(dictionary=True)
            
            # First, ensure the password_reset_tokens table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    token VARCHAR(100) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    used BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.commit()
            
            # Check if users table has email column, if not add it
            cursor.execute("SHOW COLUMNS FROM users LIKE 'email'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
                conn.commit()
            
            # Find user by username or email
            cursor.execute("""
                SELECT id, username, email FROM users 
                WHERE username = %s OR email = %s
            """, (username_or_email, username_or_email))
            user = cursor.fetchone()
            
            if user and user.get('email'):
                # Generate secure reset token
                import secrets
                import hashlib
                token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                
                # Store token in database (expires in 1 hour)
                cursor.execute("""
                    INSERT INTO password_reset_tokens (user_id, token, expires_at)
                    VALUES (%s, %s, DATE_ADD(NOW(), INTERVAL 1 HOUR))
                """, (user['id'], token_hash))
                conn.commit()
                
                # Send reset email
                reset_link = url_for('main.reset_password', token=token, _external=True)
                send_password_reset_email(user['email'], user['username'], reset_link)
                
                flash("Password reset link has been sent to your email address. Please check your inbox.", "success")
            else:
                # Don't reveal if user exists or doesn't have email
                flash("If an account exists with this information and has an email address, a password reset link will be sent.", "info")
        except Exception as e:
            import traceback
            with open("password_reset_errors.log", "a") as f:
                f.write(f"\n--- Error at {datetime.now()} ---\n")
                f.write(traceback.format_exc())
            flash("An error occurred. Please try again later.", "danger")
        finally:
            cursor.close()
        
        return redirect(url_for('main.login'))
    
    return render_template("forgot_password.html")

import time
DASHBOARD_CACHE = {'timestamp': 0, 'data': None}

@bp.route("/")
@bp.route("/dashboard")
@login_required
def index():
    global DASHBOARD_CACHE
    import time
    
    # 15 second memory cache to avoid running 8 slow DB queries back to back over a latency-heavy cloud connection
    if time.time() - DASHBOARD_CACHE['timestamp'] < 15 and DASHBOARD_CACHE['data']:
        cached = DASHBOARD_CACHE['data']
        # Refresh the current date dynamically, use everything else from cache
        cached['date'] = datetime.now().strftime("%B %d, %Y")
        return render_template("dashboard_perfect.html", **cached)
        
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Fetch Recent Visitors (Prioritize Active) - Optimized for Mobile Performance
        cursor.execute("SELECT * FROM visitors ORDER BY field(status, 'IN', 'OUT'), check_in DESC LIMIT 50")
        visitors = cursor.fetchall()
        
        # 2. Consolidated Stats Query (Efficiency Boost)
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM visitors) as total_visits,
                (SELECT COUNT(*) FROM visitors WHERE status='IN') as active_now,
                (SELECT COUNT(*) FROM visitors WHERE check_in >= CURDATE()) as today_checkins,
                (SELECT COUNT(*) FROM visitors WHERE check_out >= CURDATE() AND status='OUT') as departed_today,
                (SELECT COUNT(*) FROM visitors WHERE check_in >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)) as this_week,
                (SELECT COUNT(*) FROM visitors WHERE check_in >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)) as this_month,
                (SELECT COUNT(*) FROM sheds WHERE status='AVAILABLE') as avail_sheds,
                (SELECT COUNT(*) FROM meeting_rooms WHERE status='AVAILABLE') as avail_rooms,
                (SELECT COUNT(*) FROM meeting_rooms WHERE status='BLOCKED') as blocked_rooms,
                (SELECT COUNT(*) FROM visitors WHERE shed_id IS NOT NULL AND status='IN') as active_shed_visitors
        """)
        stats = cursor.fetchone()

        # 3. Pre-calculated Chart Data (Purpose & Hourly) - All Time
        cursor.execute("SELECT purpose, COUNT(*) as count FROM visitors GROUP BY purpose ORDER BY count DESC LIMIT 5")
        purpose_data = cursor.fetchall()
        
        cursor.execute("SELECT HOUR(check_in) as hour, COUNT(*) as count FROM visitors GROUP BY hour ORDER BY hour")
        hourly_data = cursor.fetchall()

        # 4. Trend Data (Last 30 Days - Fixed to latest)
        cursor.execute("""
            SELECT DATE_FORMAT(check_in, '%Y-%m-%d') as date, COUNT(*) as count 
            FROM visitors 
            WHERE check_in >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY date 
            ORDER BY date ASC
        """)
        trend_rows = cursor.fetchall()
        initial_counts = [r['count'] for r in trend_rows]
        initial_avg = round(sum(initial_counts)/len(initial_counts), 1) if initial_counts else 0
        initial_peak = max(initial_counts) if initial_counts else 0

        # 5. Dashboard Contextual Items (Groups & Companies)
        cursor.execute("""
            SELECT g.name, g.color,
                (SELECT COUNT(*) FROM regular_visitors r WHERE r.group_id = g.id) as member_count,
                (SELECT COUNT(*) FROM regular_visitors r JOIN visitors v ON r.phone = v.phone WHERE r.group_id = g.id AND v.status='IN') as onsite_count
            FROM visitor_groups g ORDER BY member_count DESC LIMIT 5
        """)
        dashboard_groups = cursor.fetchall()

        cursor.execute("SELECT company, COUNT(*) as count FROM visitors GROUP BY company ORDER BY count DESC LIMIT 5")
        top_companies = cursor.fetchall()

        cursor.execute("SELECT AVG(TIMESTAMPDIFF(MINUTE, check_in, check_out)) as avg_min FROM visitors WHERE status='OUT' AND check_out IS NOT NULL")
        res_avg = cursor.fetchone()
        avg_duration_global = round(res_avg['avg_min']) if res_avg and res_avg['avg_min'] else 0
        
        cursor.close()
        
        DASHBOARD_CACHE['data'] = {
            'visitors': visitors,
            'stats': stats,
            'purpose_data': purpose_data,
            'hourly_data': hourly_data,
            'chart_dates': [r['date'] for r in trend_rows],
            'chart_counts': initial_counts,
            'chart_avg': initial_avg,
            'chart_peak': initial_peak,
            'groups': dashboard_groups,
            'top_companies': top_companies,
            'avg_duration_global': avg_duration_global,
            'date': datetime.now().strftime("%B %d, %Y")
        }
        DASHBOARD_CACHE['timestamp'] = time.time()
        
        return render_template("dashboard_perfect.html", **DASHBOARD_CACHE['data'])
    except Exception as e:
        import traceback
        logging_file = "dashboard_error.log"
        with open(logging_file, "a") as f:
            f.write(f"\n--- Error at {datetime.now()} ---\n")
            f.write(traceback.format_exc())
        return f"Dashboard Error: {str(e)}", 500

@bp.route("/api/analytics/drilldown")
@login_required
def api_analytics_drilldown():
    type = request.args.get('type') # 'total', 'active', 'today', 'purpose', 'hour', 'trend', 'sheds_avail', 'rooms_ready', 'rooms_blocked', 'avg_duration', 'host', 'company'
    value = request.args.get('value')
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    data = []
    category = "visitors"
    
    if type in ['sheds_avail', 'rooms_ready', 'rooms_blocked']:
        category = "logistics"
        if type == 'sheds_avail':
            cursor.execute("SELECT id, name, status, 'SHED' as type, customer_name as extra FROM sheds WHERE status = 'AVAILABLE'")
        elif type == 'rooms_ready':
            cursor.execute("SELECT id, name, status, type, '' as extra FROM meeting_rooms WHERE status = 'AVAILABLE'")
        elif type == 'rooms_blocked':
            cursor.execute("SELECT id, name, status, type, blocked_reason as extra FROM meeting_rooms WHERE status = 'BLOCKED'")
        data = cursor.fetchall()
    else:
        query = "SELECT id, visitor_name, company, person_to_meet, purpose, status, check_in, check_out, TIMESTAMPDIFF(MINUTE, check_in, check_out) as duration FROM visitors WHERE 1=1"
        params = []
        
        if type == 'active':
            query += " AND status = 'IN'"
        elif type == 'today':
            query += " AND check_in >= CURDATE()"
        elif type == 'purpose':
            query += " AND purpose = %s AND check_in >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
            params.append(value)
        elif type == 'hour':
            query += " AND HOUR(check_in) = %s AND check_in >= DATE_SUB(NOW(), INTERVAL 30 DAY)"
            params.append(value)
        elif type == 'trend':
            query += " AND DATE(check_in) = %s"
            params.append(value)
        elif type == 'avg_duration':
            query += " AND status = 'OUT' AND check_out IS NOT NULL ORDER BY duration DESC LIMIT 50"
        elif type == 'host':
            query += " AND person_to_meet = %s ORDER BY check_in DESC"
            params.append(value)
        elif type == 'company':
            query += " AND company = %s ORDER BY check_in DESC"
            params.append(value)
        elif type == 'active_shed':
            query += " AND shed_id IS NOT NULL AND status = 'IN'"
        elif type == 'total':
            query += " ORDER BY check_in DESC LIMIT 100"
            
        if type != 'avg_duration' and type != 'total':
            query += " ORDER BY status='IN' DESC, check_in DESC"
            
        cursor.execute(query, tuple(params))
        data = cursor.fetchall()
        
        for v in data:
            v['check_in_time'] = v['check_in'].strftime('%H:%M %p') if v.get('check_in') else ''
            v['check_in_date'] = v['check_in'].strftime('%Y-%m-%d') if v.get('check_in') else ''
            v['duration'] = f"{v['duration']} min" if v.get('duration') is not None else "--"
    
    cursor.close()
    return jsonify({"category": category, "data": data, "type": type, "value": value})

@bp.route("/api/visitor/details/<int:id>")
@login_required
def api_visitor_details(id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch visitor with group name
    cursor.execute("""
        SELECT v.*, g.name as group_name 
        FROM visitors v 
        LEFT JOIN visitor_groups g ON v.group_id = g.id 
        WHERE v.id = %s
    """, (id,))
    visitor = cursor.fetchone()
    
    if visitor:
        # Get total visits by this phone number
        phone = visitor.get('phone')
        if phone:
            cursor.execute("SELECT COUNT(*) as total FROM visitors WHERE phone = %s", (phone,))
            visitor['total_visits'] = cursor.fetchone()['total']
        else:
            visitor['total_visits'] = 1

        # Format dates for JSON
        if visitor.get('check_in'):
            visitor['check_in_iso'] = visitor['check_in'].isoformat()
            visitor['check_in_time'] = visitor['check_in'].strftime('%H:%M')
            visitor['check_in_date'] = visitor['check_in'].strftime('%Y-%m-%d')
        if visitor.get('check_out'):
            visitor['check_out_iso'] = visitor['check_out'].isoformat()
            
    cursor.close()
    if visitor:
        return jsonify(visitor)
    return jsonify({"error": "Visitor not found"}), 404

@bp.route("/mobile-connect")
@login_required
def mobile_connect():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()
    
    # Get port from request or default to 5000
    port = request.host.split(':')[-1] if ':' in request.host else '5000'
    
    # Construct the URL for mobile access
    # Use https since run.py uses adhoc ssl
    mobile_url = f"https://{local_ip}:{port}/"
    
    return render_template("mobile_connect.html", mobile_url=mobile_url)

@bp.route("/api/chart-data/<int:days>")
@login_required
def chart_data_api(days):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    
    if start_date and end_date:
        query = """
            SELECT DATE_FORMAT(check_in, '%Y-%m-%d') as date, COUNT(*) as count 
            FROM visitors 
            WHERE DATE(check_in) >= %s AND DATE(check_in) <= %s 
            GROUP BY date 
            ORDER BY date ASC
        """
        cursor.execute(query, (start_date, end_date))
    else:
        # Bound the days to reasonable values if no custom range
        days = max(1, min(days, 365)) # Increased limit to 365
        query = """
            SELECT DATE_FORMAT(check_in, '%Y-%m-%d') as date, COUNT(*) as count 
            FROM visitors 
            WHERE check_in >= DATE_SUB(NOW(), INTERVAL %s DAY) 
            GROUP BY date 
            ORDER BY date ASC
        """
        cursor.execute(query, (days,))
    
    chart_data = cursor.fetchall()
    
    dates = [row['date'] for row in chart_data]
    counts = [row['count'] for row in chart_data]
    
    # Fill empty if needed (only for period-based, custom range might have gaps)
    if not dates and not (start_date and end_date):
        dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(days, 0, -1)]
        counts = [0] * days
        
    # Fetch visitors for this period (Limit 50)
    v_query = ""
    v_params = ()
    if start_date and end_date:
        v_query = "SELECT * FROM visitors WHERE DATE(check_in) >= %s AND DATE(check_in) <= %s ORDER BY check_in DESC LIMIT 50"
        v_params = (start_date, end_date)
    else:
        v_query = "SELECT * FROM visitors WHERE check_in >= DATE_SUB(NOW(), INTERVAL %s DAY) ORDER BY check_in DESC LIMIT 50"
        v_params = (days,)
        
    cursor.execute(v_query, v_params)
    visitors = cursor.fetchall()
    
    cursor.close()
    return jsonify({
        "dates": dates, 
        "counts": counts,
        "avg": round(sum(counts)/len(counts), 1) if counts else 0,
        "peak": max(counts) if counts else 0,
        "total": sum(counts),
        "visitors": visitors
    })

@bp.route("/chat/message", methods=["POST"])
@login_required
def chat_message():
    data = request.get_json()
    user_message = data.get("message", "")
    response_data = process_message(user_message, session.get('user_id'))
    return jsonify(response_data)


@bp.route("/logs")
@login_required
def logs():
    status_filter = request.args.get('status')
    search_query = request.args.get('search')
    date_filter = request.args.get('date')
    company_filter = request.args.get('company')
    host_filter = request.args.get('host')
    purpose_filter = request.args.get('purpose')
    
    query = """
        SELECT v.*, 
               rv.id as regular_id, 
               vg.name as group_name,
               u.phone as host_phone,
               (SELECT COUNT(*) FROM visitors v2 WHERE v2.phone = rv.phone AND rv.phone IS NOT NULL AND rv.phone != '') as visit_count
        FROM visitors v
        LEFT JOIN regular_visitors rv ON v.phone = rv.phone AND v.phone IS NOT NULL AND v.phone != ''
        LEFT JOIN visitor_groups vg ON rv.group_id = vg.id
        LEFT JOIN users u ON (u.full_name = v.person_to_meet OR u.username = v.person_to_meet)
        WHERE 1=1
    """
    params = []
    
    if status_filter:
        query += " AND v.status = %s"
        params.append(status_filter)
    
    if date_filter:
        query += " AND DATE(v.check_in) = %s"
        params.append(date_filter)

    if company_filter:
        query += " AND v.company = %s"
        params.append(company_filter)

    if host_filter:
        query += " AND v.person_to_meet = %s"
        params.append(host_filter)

    if purpose_filter:
        query += " AND v.purpose = %s"
        params.append(purpose_filter)
        
    if search_query:
        query += " AND (v.visitor_name LIKE %s OR v.company LIKE %s OR v.person_to_meet LIKE %s OR v.purpose LIKE %s)"
        wild = f"%{search_query}%"
        params.extend([wild, wild, wild, wild])
        
    query += " ORDER BY v.check_in DESC LIMIT 500"
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, tuple(params))
    visitors = cursor.fetchall()
    cursor.close()
    
    return render_template("logs.html", 
                         visitors=visitors, 
                         current_filter=status_filter, 
                         date_filter=date_filter,
                         company_filter=company_filter,
                         host_filter=host_filter,
                         purpose_filter=purpose_filter)

@bp.route("/export")
@login_required
def export_csv():
    # Get filter parameters from query string
    status_filter = request.args.get('status')
    search_query = request.args.get('search')
    date_filter = request.args.get('date')
    purpose_filter = request.args.get('purpose')
    company_filter = request.args.get('company')
    days_filter = request.args.get('days', type=int)
    
    # Build dynamic query with filters
    query = "SELECT * FROM visitors WHERE 1=1"
    params = []
    
    if status_filter:
        query += " AND status = %s"
        params.append(status_filter)
    
    if date_filter:
        query += " AND DATE(check_in) = %s"
        params.append(date_filter)

    if days_filter is not None:
        if days_filter == 0:
            query += " AND DATE(check_in) = CURDATE()"
        elif days_filter == 1:
            query += " AND DATE(check_in) = SUBDATE(CURDATE(), 1)"
        else:
            query += " AND check_in >= DATE(NOW()) - INTERVAL %s DAY"
            params.append(days_filter)
    
    if purpose_filter:
        query += " AND purpose = %s"
        params.append(purpose_filter)

    if company_filter:
        query += " AND company = %s"
        params.append(company_filter)
        
    if search_query:
        query += " AND (visitor_name LIKE %s OR company LIKE %s OR person_to_meet LIKE %s OR purpose LIKE %s)"
        wild = f"%{search_query}%"
        params.extend([wild, wild, wild, wild])
        
    query += " ORDER BY check_in DESC"
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, tuple(params))
    visitors = cursor.fetchall()
    cursor.close()
    
    # Generate CSV
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Visitor Name', 'Company', 'Phone', 'Purpose', 'Host', 'Check In', 'Check Out', 'Status'])
    
    for v in visitors:
        cw.writerow([
            v['id'], v['visitor_name'], v['company'], v['phone'], 
            v['purpose'], v['person_to_meet'], 
            v['check_in'], v['check_out'], v['status']
        ])
        
    output = si.getvalue()
    
    # Generate filename with filter info
    filename = "visitor_logs"
    if status_filter:
        filename += f"_{status_filter}"
    if date_filter:
        filename += f"_{date_filter}"
    if days_filter:
        filename += f"_last_{days_filter}_days"
    if purpose_filter:
        filename += f"_{purpose_filter}"
    if company_filter:
        filename += f"_{company_filter}"
    if search_query:
        filename += f"_{search_query.replace(' ', '_')}"
            
    filename += ".csv"
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@bp.route("/add", methods=["GET", "POST"])
@login_required
def add_visitor():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = '127.0.0.1'
    finally:
        s.close()

    import os
    security_policies = ""
    protocol_path = os.path.join(os.path.dirname(__file__), 'security_protocol.html')
    if os.path.exists(protocol_path):
        try:
            with open(protocol_path, 'r', encoding='utf-8') as f:
                security_policies = f.read()
        except Exception as e:
            print(f"Error reading security protocol: {e}")
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # Ensure visitor_form_settings table exists
    ensure_visitor_form_settings()
    # Ensure draft columns exist
    ensure_draft_column()
    
    cursor.execute("SELECT * FROM visitor_groups ORDER BY name")
    groups = cursor.fetchall()
    
    # Fetch Form Settings
    cursor.execute("SELECT * FROM visitor_form_settings")
    settings_rows = cursor.fetchall()
    field_settings = {row['field_key']: {'required': row['is_required'], 'visible': row['is_visible']} for row in settings_rows}

    # Check if 'General' group exists, if not create it
    if not any(g['name'] == 'General' for g in groups):
        cursor.execute("INSERT INTO visitor_groups (name, description, color) VALUES ('General', 'Default Group', 'secondary')")
        conn.commit()
        cursor.execute("SELECT * FROM visitor_groups ORDER BY name")
        groups = cursor.fetchall()
    
    # Fetch all drafts for display
    try:
        cursor.execute("""
            SELECT v.*, u.username as created_by_name 
            FROM visitors v 
            LEFT JOIN users u ON v.draft_created_by = u.id
            WHERE v.is_draft = 1 
            ORDER BY v.draft_created_at DESC
        """)
        drafts = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching drafts: {e}")
        drafts = []
    
    # Check if editing a draft
    draft_id = request.args.get('draft_id')
    draft_data = None
    if draft_id:
        cursor.execute("SELECT * FROM visitors WHERE id = %s AND is_draft = 1", (draft_id,))
        draft_data = cursor.fetchone()
    
    cursor.execute("SELECT * FROM sheds")
    all_sheds = cursor.fetchall()
    
    cursor.close()
    
    prefill_name = request.args.get('visitor_name', '')

    if request.method == "POST":
        try:
            # Check if this is a draft save or activation
            action = request.form.get("action", "checkin")  # 'draft' or 'checkin' or 'activate'
            draft_notes = request.form.get("draft_notes", "")
            editing_draft_id = request.form.get("draft_id")
            
            # Debug logging
            print(f"🔍 DEBUG: Action received = '{action}'")
            print(f"🔍 DEBUG: Draft ID = '{editing_draft_id}'")
            
            visitor_name = request.form.get("visitor_name")
            company = request.form.get("company")
            phone = request.form.get("phone")
            email = request.form.get("email")
            photo = request.form.get("photo") 
            custom_qr = request.form.get("custom_qr")
            id_card_photo = request.form.get("id_card_photo")
            signature = request.form.get("signature")
            document_signed = 1 if signature else 0
            visitor_type = request.form.get("visitor_type", "Guest")
            vehicle_number = request.form.get("vehicle_number")
            shed_id = request.form.get("shed_id")
            equipment_details = request.form.get("equipment_details")
            expected_duration = request.form.get("expected_duration")
            emergency_contact = request.form.get("emergency_contact")
            id_type = request.form.get("id_type", "National ID")
            safety_induction_agreed = 1 if request.form.get("safety_induction") == "on" else 0
            visit_priority = request.form.get("visit_priority", "Normal")
            laptop_serial = request.form.get("laptop_serial")
            additional_visitors_count = request.form.get("additional_visitors_count", 0)
            health_declaration_clear = 1 if request.form.get("health_clear") == "on" else 0
            
            purpose = request.form.get("purpose")
            person_to_meet = request.form.get("person_to_meet")

            assign_group_id = request.form.get("assign_group_id")
            
            # New Customer Features
            pickup_required = 1 if request.form.get("pickup_required") == "on" else 0
            drop_required = 1 if request.form.get("drop_required") == "on" else 0
            food_order_details = request.form.get("food_order_details", "")
            engage_driver = 1 if request.form.get("engage_driver") == "on" else 0
            assigned_department_email = request.form.get("assigned_department_email", "")

            # Logistics & Transport Extended Fields
            pickup_from_location = request.form.get("pickup_from_location") or None
            pickup_to_location = request.form.get("pickup_to_location") or None
            pickup_time = request.form.get("pickup_time") or None
            
            drop_from_location = request.form.get("drop_from_location") or None
            drop_to_location = request.form.get("drop_to_location") or None
            drop_time = request.form.get("drop_time") or None
            
            ac_count = request.form.get("accompanying_members_count")
            accompanying_members_count = int(ac_count) if ac_count and ac_count.isdigit() else 0
            accompanying_members_names = request.form.get("accompanying_members_names") or None
            
            assign_badges = request.form.get("assign_badges_to_members") == "1"
            sub_members = []
            if assign_badges and accompanying_members_count > 0:
                for idx in range(accompanying_members_count):
                    m_name = request.form.get(f"member_name_{idx}")
                    m_email = request.form.get(f"member_email_{idx}")
                    if m_name:
                        sub_members.append({"name": m_name, "email": m_email})

            # For drafts, only visitor_name is required
            if action == "draft":
                if not visitor_name:
                    flash("Visitor name is required for drafts.", "warning")
                    return redirect(url_for("main.add_visitor"))
            else:
                # For check-in, all required fields must be filled
                if not visitor_name or not phone or not person_to_meet:
                    flash("Please fill in all required fields.", "warning")
                    return redirect(url_for("main.add_visitor"))

            conn = get_db()
            cursor = conn.cursor()
            
            if action == "draft":
                if editing_draft_id:
                    # Update existing draft
                    cursor.execute("""
                        UPDATE visitors SET
                        visitor_name = %s, company = %s, phone = %s, email = %s, photo = %s, custom_qr = %s,
                        id_card_photo = %s, signature = %s, document_signed = %s, purpose = %s, person_to_meet = %s,
                        group_id = %s, regular_visitor_id = %s,
                        visitor_type = %s, vehicle_number = %s, equipment_details = %s, expected_duration = %s,
                        emergency_contact = %s, id_type = %s, safety_induction_agreed = %s, visit_priority = %s,
                        laptop_serial = %s, additional_visitors_count = %s, health_declaration_clear = %s,
                        draft_notes = %s, shed_id = %s,
                        pickup_required = %s, drop_required = %s, food_order_details = %s, engage_driver = %s, assigned_department_email = %s,
                        pickup_from_location = %s, pickup_to_location = %s, pickup_time = %s, drop_from_location = %s, drop_to_location = %s, drop_time = %s,
                        accompanying_members_count = %s, accompanying_members_names = %s
                        WHERE id = %s AND is_draft = 1
                    """, (visitor_name, company, phone, email, photo, custom_qr, id_card_photo, signature, document_signed,
                          purpose, person_to_meet, assign_group_id if assign_group_id else None, request.args.get("regular_id") or None,
                          visitor_type, vehicle_number, equipment_details, expected_duration, emergency_contact,
                          id_type, safety_induction_agreed, visit_priority, laptop_serial,
                          additional_visitors_count, health_declaration_clear, draft_notes,
                          shed_id if shed_id else None,
                          pickup_required, drop_required, food_order_details, engage_driver, assigned_department_email,
                          pickup_from_location, pickup_to_location, pickup_time, drop_from_location, drop_to_location, drop_time,
                          accompanying_members_count, accompanying_members_names,
                          editing_draft_id))
                    conn.commit()
                    draft_id = editing_draft_id
                else:
                    # Save as draft
                    cursor.execute("""
                        INSERT INTO visitors
                        (visitor_name, company, phone, email, photo, custom_qr, id_card_photo, signature, document_signed, 
                         purpose, person_to_meet, status, check_in, group_id, regular_visitor_id,
                         visitor_type, vehicle_number, equipment_details, expected_duration, emergency_contact,
                         id_type, safety_induction_agreed, visit_priority, laptop_serial, 
                         additional_visitors_count, health_declaration_clear,
                         is_draft, draft_created_by, draft_created_at, draft_notes, shed_id,
                         pickup_required, drop_required, food_order_details, engage_driver, assigned_department_email,
                         pickup_from_location, pickup_to_location, pickup_time, drop_from_location, drop_to_location, drop_time,
                         accompanying_members_count, accompanying_members_names)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'DRAFT', NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (visitor_name, company, phone, email, photo, custom_qr, id_card_photo, signature, document_signed, 
                          purpose, person_to_meet, assign_group_id if assign_group_id else None, request.args.get("regular_id") or None,
                          visitor_type, vehicle_number, equipment_details, expected_duration, emergency_contact,
                          id_type, safety_induction_agreed, visit_priority, laptop_serial, 
                          additional_visitors_count, health_declaration_clear,
                          session.get('user_id'), draft_notes, shed_id if shed_id else None,
                          pickup_required, drop_required, food_order_details, engage_driver, assigned_department_email,
                          pickup_from_location, pickup_to_location, pickup_time, drop_from_location, drop_to_location, drop_time,
                          accompanying_members_count, accompanying_members_names))
                    conn.commit()
                    draft_id = cursor.lastrowid
                
                if sub_members:
                    for sm in sub_members:
                        cursor.execute("""
                            INSERT INTO visitors (visitor_name, company, phone, email, purpose, person_to_meet, status, is_draft, draft_created_by, draft_created_at, visitor_type)
                            VALUES (%s, %s, %s, %s, %s, %s, 'DRAFT', 1, %s, NOW(), %s)
                        """, (sm['name'], (company or '') + " (Group)", phone, sm['email'], purpose, person_to_meet, session.get('user_id'), visitor_type))
                    conn.commit()
                
                cursor.close()
                flash(f"Draft saved successfully for {visitor_name}. You can activate it when the visitor arrives.", "success")
                return redirect(url_for("main.add_visitor"))
                
            elif action == "pre_register":
                # Pre-register awaiting host approval
                cursor.execute("""
                    INSERT INTO visitors
                    (visitor_name, company, phone, email, photo, custom_qr, id_card_photo, signature, document_signed, 
                     purpose, person_to_meet, status, host_approval_status, check_in, group_id, regular_visitor_id,
                     visitor_type, vehicle_number, equipment_details, expected_duration, emergency_contact,
                     id_type, safety_induction_agreed, visit_priority, laptop_serial, 
                     additional_visitors_count, health_declaration_clear,
                     is_draft, draft_created_by, draft_created_at, draft_notes, shed_id,
                     pickup_required, drop_required, food_order_details, engage_driver, assigned_department_email,
                     pickup_from_location, pickup_to_location, pickup_time, drop_from_location, drop_to_location, drop_time,
                     accompanying_members_count, accompanying_members_names)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PRE_REGISTERED', 'PENDING', NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (visitor_name, company, phone, email, photo, custom_qr, id_card_photo, signature, document_signed, 
                      purpose, person_to_meet, assign_group_id if assign_group_id else None, request.args.get("regular_id") or None,
                      visitor_type, vehicle_number, equipment_details, expected_duration, emergency_contact,
                      id_type, safety_induction_agreed, visit_priority, laptop_serial, 
                      additional_visitors_count, health_declaration_clear,
                      session.get('user_id'), draft_notes, shed_id if shed_id else None,
                      pickup_required, drop_required, food_order_details, engage_driver, assigned_department_email,
                      pickup_from_location, pickup_to_location, pickup_time, drop_from_location, drop_to_location, drop_time,
                      accompanying_members_count, accompanying_members_names))
                conn.commit()
                
                if sub_members:
                    for sm in sub_members:
                        cursor.execute("""
                            INSERT INTO visitors (visitor_name, company, phone, email, purpose, person_to_meet, status, host_approval_status, is_draft, draft_created_by, draft_created_at, visitor_type)
                            VALUES (%s, %s, %s, %s, %s, %s, 'PRE_REGISTERED', 'PENDING', 0, %s, NOW(), %s)
                        """, (sm['name'], (company or '') + " (Group)", phone, sm['email'], purpose, person_to_meet, session.get('user_id'), visitor_type))
                    conn.commit()
                    
                cursor.close()
                flash(f"Pre-registration submitted successfully for {visitor_name}. Currently awaiting host approval from {person_to_meet}.", "success")
                return redirect(url_for("main.add_visitor"))
                
            elif action == "activate" and editing_draft_id:
                # Activate existing draft
                cursor.execute("""
                    UPDATE visitors SET
                    visitor_name = %s, company = %s, phone = %s, email = %s, photo = %s, custom_qr = %s,
                    id_card_photo = %s, signature = %s, document_signed = %s, purpose = %s, person_to_meet = %s,
                    status = 'IN', check_in = NOW(), group_id = %s, regular_visitor_id = %s,
                    visitor_type = %s, vehicle_number = %s, equipment_details = %s, expected_duration = %s,
                    emergency_contact = %s, id_type = %s, safety_induction_agreed = %s, visit_priority = %s,
                    laptop_serial = %s, additional_visitors_count = %s, health_declaration_clear = %s,
                    is_draft = 0, draft_notes = %s, shed_id = %s,
                    pickup_required = %s, drop_required = %s, food_order_details = %s, engage_driver = %s, assigned_department_email = %s,
                    pickup_from_location = %s, pickup_to_location = %s, pickup_time = %s, drop_from_location = %s, drop_to_location = %s, drop_time = %s,
                    accompanying_members_count = %s, accompanying_members_names = %s
                    WHERE id = %s AND is_draft = 1
                """, (visitor_name, company, phone, email, photo, custom_qr, id_card_photo, signature, document_signed,
                      purpose, person_to_meet, assign_group_id if assign_group_id else None, request.args.get("regular_id") or None,
                      visitor_type, vehicle_number, equipment_details, expected_duration, emergency_contact,
                      id_type, safety_induction_agreed, visit_priority, laptop_serial,
                      additional_visitors_count, health_declaration_clear, draft_notes, 
                    shed_id if shed_id else None,
                    pickup_required, drop_required, food_order_details, engage_driver, assigned_department_email,
                    pickup_from_location, pickup_to_location, pickup_time, drop_from_location, drop_to_location, drop_time,
                    accompanying_members_count, accompanying_members_names,
                    editing_draft_id))
                conn.commit()
                visitor_id = int(editing_draft_id)
                cursor.close()
                
                # Send badge email if email provided
                if email:
                    base_url = url_for('main.badge', id=visitor_id, _external=True)
                    badge_url = base_url.replace('localhost', local_ip).replace('127.0.0.1', local_ip)
                    visitor_code = f"VIS-{visitor_id:06d}"
                    send_badge_email(email, visitor_name, visitor_code, badge_url, "Check-In", company)
                

                
                flash(f"Draft activated! Visitor {visitor_name} checked in successfully.", "success")
                return redirect(url_for("main.badge", id=visitor_id))
            else:
                # Regular check-in
                cursor.execute("""
                    INSERT INTO visitors
                    (visitor_name, company, phone, email, photo, custom_qr, id_card_photo, signature, document_signed, 
                     purpose, person_to_meet, status, check_in, group_id, regular_visitor_id,
                     visitor_type, vehicle_number, equipment_details, expected_duration, emergency_contact,
                     id_type, safety_induction_agreed, visit_priority, laptop_serial, 
                     additional_visitors_count, health_declaration_clear, shed_id,
                     pickup_required, drop_required, food_order_details, engage_driver, assigned_department_email,
                     pickup_from_location, pickup_to_location, pickup_time, drop_from_location, drop_to_location, drop_time,
                     accompanying_members_count, accompanying_members_names)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'IN', NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (visitor_name, company, phone, email, photo, custom_qr, id_card_photo, signature, document_signed, 
                      purpose, person_to_meet, assign_group_id if assign_group_id else None, request.args.get("regular_id") or None,
                      visitor_type, vehicle_number, equipment_details, expected_duration, emergency_contact,
                      id_type, safety_induction_agreed, visit_priority, laptop_serial, 
                      additional_visitors_count, health_declaration_clear, shed_id if shed_id else None,
                      pickup_required, drop_required, food_order_details, engage_driver, assigned_department_email,
                      pickup_from_location, pickup_to_location, pickup_time, drop_from_location, drop_to_location, drop_time,
                      accompanying_members_count, accompanying_members_names))
                conn.commit()
                visitor_id = cursor.lastrowid
                
                # Check-in accompanying members
                checked_in_members = []
                if sub_members:
                    for sm in sub_members:
                        cursor.execute("""
                            INSERT INTO visitors (visitor_name, company, phone, email, purpose, person_to_meet, status, check_in, host_approval_status, is_draft, visitor_type)
                            VALUES (%s, %s, %s, %s, %s, %s, 'IN', NOW(), 'APPROVED', 0, %s)
                        """, (sm['name'], (company or '') + " (Group)", phone, sm['email'], purpose, person_to_meet, visitor_type))
                        checked_in_members.append((cursor.lastrowid, sm['email'], sm['name']))
                    conn.commit()
                    
                cursor.close()

                # Forward badge via email if email is provided
                if email:
                    # Ensure the URL is accessible from mobile devices on the network
                    base_url = url_for('main.badge', id=visitor_id, _external=True)
                    badge_url = base_url.replace('localhost', local_ip).replace('127.0.0.1', local_ip)
                    
                    visitor_code = f"VIS-{visitor_id:06d}"
                    send_badge_email(email, visitor_name, visitor_code, badge_url, "Check-In", company)
                
                for cm_id, cm_email, cm_name in checked_in_members:
                    if cm_email:
                        cm_badge_url = url_for('main.badge', id=cm_id, _external=True).replace('localhost', local_ip).replace('127.0.0.1', local_ip)
                        send_badge_email(cm_email, cm_name, f"VIS-{cm_id:06d}", cm_badge_url, "Check-In", (company or '') + " (Group)")

                # Send department alert if provided
                if assigned_department_email:
                    dept_emails = [e.strip() for e in assigned_department_email.split(',') if e.strip()]
                    for de in dept_emails:
                        send_department_alert_email(de, visitor_name, company, purpose, person_to_meet)

                flash(f"Visitor {visitor_name} registered successfully.", "success")
                return redirect(url_for("main.badge", id=visitor_id))
            
        except Exception as e:
            import traceback
            with open("debug_registration.log", "a") as f:
                f.write(f"\n--- Error at {datetime.now()} ---\n")
                f.write(traceback.format_exc())
            flash(f"Oops! Registration failed: {str(e)}", "danger")
            return redirect(url_for("main.add_visitor"))

    # All roles including SECURITY get the full-featured add_visitor form.
    # The sidebar is already filtered for SECURITY via the inject_sidebar_menu context processor
    # (only 'dashboard', 'logs', 'add' are shown — no groups/dmt/menu maintenance).
    return render_template("add_visitor.html", 
                         local_ip=local_ip, 
                         groups=groups, 
                         now=datetime.now(), 
                         timedelta=timedelta, 
                         visitors=[], 
                         security_policies=security_policies,
                         field_settings=field_settings,
                         drafts=drafts,
                         draft_data=draft_data,
                         prefill_name=prefill_name,
                         all_sheds=all_sheds)


def send_badge_email(to_email, visitor_name, visitor_code, badge_url, state, company=""):
    """
    Utility function to send badge via email using dynamically configured SMTP settings.
    Sends beautifully styled HTML emails for both Check-In (Access) and Check-Out (Receipt).
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import urllib.parse

    # --- FETCH SMTP SETTINGS FROM DB ---
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM smtp_settings WHERE status = 1 LIMIT 1")
    settings = cursor.fetchone()
    cursor.close()
    
    # Define Details & Theme based on State ('Check-In' vs 'Check-Out')
    is_checkout = (state == "Check-Out")
    
    if is_checkout:
        theme_color = "#475569" # Slate for neutral/done
        accent_gradient = "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)" # Dark Professional
        status_color = "#ef4444" # Red
        status_text = "VISIT CONCLUDED"
        headline = "Visit Receipt"
        subhead = "Your visit has been successfully completed. Thank you."
        action_text = "View Digital Record"
        icon_class = "bi-box-arrow-right"
    else:
        theme_color = "#2563eb" # Blue
        accent_gradient = "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)" # Bright Blue
        status_color = "#22c55e" # Green
        status_text = "ACCESS AUTHORIZED"
        headline = "Visitor Access Pass"
        subhead = "Please present this pass at the security checkpoint."
        action_text = "Open Digital Badge"
        icon_class = "bi-shield-check"

    if not settings:
        # Fallback to simulation mode if no settings configured
        with open("email_logs.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- Email Simulation ({datetime.now()}) [NO SMTP CONFIG] ---\n")
            f.write(f"To: {to_email}\nSubject: {headline}: {visitor_name}\nCompany: {company}\nBody: Link: {badge_url}\n")
        return True

    SMTP_SERVER = settings['server']
    SMTP_PORT = settings['port']
    SMTP_USER = settings['username']
    SMTP_PASS = settings['password']
    # --------------------------

    subject = f"{'✅' if not is_checkout else '🛑'} {headline}: {visitor_name} - {company}"
    
    # Generate QR Code for email body
    encoded_url = urllib.parse.quote(badge_url)
    qr_image_url = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={encoded_url}&color=000000&bgcolor=FFFFFF"

    # 1. Plain Text Version (Fallback)
    text_body = f"""
    {headline}
    =========================
    Visitor: {visitor_name}
    Company: {company}
    Status: {status_text}
    
    {subhead}
    
    Visitor ID: {visitor_code}
    Date: {datetime.now().strftime('%d %B %Y')}
    
    Access Digital Badge:
    {badge_url}
    
    Securely,
    Visitor Management System
    """

    # 2. Beautiful HTML Version
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{headline}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9; -webkit-font-smoothing: antialiased;">
        
        <!-- Main Container -->
        <div style="max-width: 500px; margin: 40px auto; background-color: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 15px 35px rgba(0,0,0,0.08); border: 1px solid #e2e8f0;">
            
            <!-- Header Badge -->
            <div style="background: {accent_gradient}; padding: 35px 30px; text-align: center; color: #ffffff;">
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2.5px; opacity: 0.85; margin-bottom: 10px;">Visitor Portal System</div>
                <div style="font-size: 28px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 5px; text-shadow: 0 2px 4px rgba(0,0,0,0.1);">{headline}</div>
                <div style="font-size: 15px; opacity: 0.95; font-weight: 500;">{subhead}</div>
            </div>

            <!-- Content Body -->
            <div style="padding: 35px 30px; text-align: center;">
                
                <!-- Visitor Identity -->
                <div style="margin-bottom: 25px;">
                    <div style="font-size: 26px; font-weight: 800; color: #0f172a; line-height: 1.2;">{visitor_name}</div>
                    <div style="font-size: 16px; font-weight: 600; color: #64748b; margin-top: 5px;">{company if company else 'Authorized Visitor'}</div>
                </div>

                <!-- Status Pill -->
                <div style="margin-bottom: 30px;">
                     <span style="background-color: {status_color}10; color: {status_color}; padding: 8px 18px; border-radius: 50px; font-size: 12px; font-weight: 800; text-transform: uppercase; border: 1px solid {status_color}30; letter-spacing: 1px; display: inline-block;">
                        • {status_text} •
                     </span>
                </div>

                <!-- QR Code Box -->
                <div style="background: #ffffff; padding: 15px; border-radius: 16px; display: inline-block; border: 2px dashed #cbd5e1; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.03);">
                    <img src="{qr_image_url}" alt="Access Code" style="display: block; width: 160px; height: 160px; border-radius: 4px;">
                    <div style="margin-top: 10px; font-size: 12px; font-weight: 700; color: #64748b; font-family: monospace; letter-spacing: 1px;">
                        {visitor_code}
                    </div>
                </div>
                
                <!-- Info Grid -->
                <div style="background-color: #f8fafc; border-radius: 12px; padding: 20px; text-align: left; border: 1px solid #e2e8f0;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding-bottom: 12px; width: 40%; font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 2.5px; opacity: 0.85;">Timestamp</td>
                            <td style="padding-bottom: 12px; font-size: 14px; color: #334155; font-weight: 600; text-align: right;">
                                {datetime.now().strftime('%H:%M | %d %b %Y')}
                            </td>
                        </tr>
                        <tr style="border-top: 1px solid #e2e8f0;">
                            <td style="padding-top: 12px; width: 40%; font-size: 11px; color: #94a3b8; font-weight: 700; text-transform: uppercase; letter-spacing: 2.5px; opacity: 0.85;">Reference ID</td>
                            <td style="padding-top: 12px; font-size: 14px; color: #334155; font-weight: 600; text-align: right; font-family: monospace;">
                                {visitor_code}
                            </td>
                        </tr>
                    </table>
                </div>

                <!-- CTA Button -->
                <div style="margin-top: 35px;">
                    <a href="{badge_url}" style="background-color: {theme_color}; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 50px; font-weight: 700; font-size: 14px; display: inline-block; box-shadow: 0 8px 16px -4px {theme_color}60; transition: transform 0.2s;">
                        {action_text} &rarr;
                    </a>
                </div>

            </div>

            <!-- Footer -->
            <div style="background-color: #f8fafc; padding: 20px; text-align: center; border-top: 1px solid #e2e8f0;">
                <p style="font-size: 11px; color: #94a3b8; margin: 0; line-height: 1.6;"> 
                    <strong>Secure Visitor Verification</strong><br>
                    Please do not share this credential with unauthorized personnel.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart('alternative')
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        
        # Log success for debugging
        with open("email_logs.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- Email Sent Successfully ({datetime.now()}) ---\n")
            f.write(f"To: {to_email}\nSubject: {subject}\n")
            
        return True
    except Exception as e:
        import traceback
        with open("email_errors.log", "a", encoding="utf-8") as f:
            f.write(f"--- Error at {datetime.now()} ---\n")
            f.write(f"Failed to send email to {to_email}: {str(e)}\n\n")
            f.write(traceback.format_exc())
            f.write("\n----------------------------\n")
        return False



def send_password_reset_email(to_email, username, reset_link):
    """
    Send a beautiful password reset email with a secure reset link.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    # Fetch SMTP settings from DB
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM smtp_settings WHERE status = 1 LIMIT 1")
    settings = cursor.fetchone()
    cursor.close()

    if not settings:
        # Fallback to simulation mode
        with open("email_logs.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- Password Reset Email Simulation ({datetime.now()}) ---\n")
            f.write(f"To: {to_email}\nUsername: {username}\nReset Link: {reset_link}\n")
        return True

    SMTP_SERVER = settings['server']
    SMTP_PORT = settings['port']
    SMTP_USER = settings['username']
    SMTP_PASS = settings['password']

    subject = f"🔐 Password Reset Request - Visitor Portal"

    # Plain text version
    text_body = f"""
    Password Reset Request
    ======================
    
    Hello {username},
    
    We received a request to reset your password for the Visitor Portal.
    
    Click the link below to reset your password (valid for 1 hour):
    {reset_link}
    
    If you didn't request this, please ignore this email.
    
    Securely,
    Visitor Portal System
    """

    # Beautiful HTML version
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f1f5f9;">
        
        <div style="max-width: 500px; margin: 40px auto; background-color: #ffffff; border-radius: 20px; overflow: hidden; box-shadow: 0 15px 35px rgba(0,0,0,0.08); border: 1px solid #e2e8f0;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); padding: 35px 30px; text-align: center; color: #ffffff;">
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2.5px; opacity: 0.85; margin-bottom: 10px;">Visitor Portal System</div>
                <div style="font-size: 28px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 5px; text-shadow: 0 2px 4px rgba(0,0,0,0.1);">Password Reset</div>
                <div style="font-size: 15px; opacity: 0.95; font-weight: 500;">Secure your account</div>
            </div>

            <!-- Content -->
            <div style="padding: 35px 30px;">
                
                <div style="margin-bottom: 25px;">
                    <div style="font-size: 16px; color: #334155; line-height: 1.6;">
                        Hello <strong>{username}</strong>,
                    </div>
                </div>

                <div style="margin-bottom: 25px;">
                    <div style="font-size: 15px; color: #64748b; line-height: 1.7;">
                        We received a request to reset your password for the Visitor Portal. Click the button below to create a new password.
                    </div>
                </div>

                <!-- Info Box -->
                <div style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(37, 99, 235, 0.1) 100%); border-left: 4px solid #3b82f6; padding: 15px 20px; border-radius: 12px; margin-bottom: 25px;">
                    <div style="font-size: 13px; color: #1e40af; line-height: 1.6;">
                        <strong>⏱️ This link expires in 1 hour</strong><br>
                        For security reasons, this reset link will only work once.
                    </div>
                </div>

                <!-- Reset Button -->
                <div style="text-align: center; margin: 35px 0;">
                    <a href="{reset_link}" style="background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 50px; font-weight: 700; font-size: 14px; display: inline-block; box-shadow: 0 8px 16px -4px rgba(245, 158, 11, 0.6);">
                        Reset My Password →
                    </a>
                </div>

                <!-- Alternative Link -->
                <div style="margin-top: 25px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                    <div style="font-size: 12px; color: #94a3b8; line-height: 1.6; text-align: center;">
                        If the button doesn't work, copy and paste this link into your browser:<br>
                        <a href="{reset_link}" style="color: #3b82f6; word-break: break-all;">{reset_link}</a>
                    </div>
                </div>

                <!-- Warning -->
                <div style="background-color: #fef2f2; border-left: 4px solid #ef4444; padding: 15px 20px; border-radius: 12px; margin-top: 25px;">
                    <div style="font-size: 13px; color: #991b1b; line-height: 1.6;">
                        <strong>⚠️ Didn't request this?</strong><br>
                        If you didn't request a password reset, please ignore this email. Your password will remain unchanged.
                    </div>
                </div>

            </div>

            <!-- Footer -->
            <div style="background-color: #f8fafc; padding: 20px; text-align: center; border-top: 1px solid #e2e8f0;">
                <p style="font-size: 11px; color: #94a3b8; margin: 0; line-height: 1.6;">
                    <strong>Secure Password Reset</strong><br>
                    This is an automated message from Visitor Portal System.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart('alternative')
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()

        with open("email_logs.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- Password Reset Email Sent ({datetime.now()}) ---\n")
            f.write(f"To: {to_email}\nUsername: {username}\n")

        return True
    except Exception as e:
        import traceback
        with open("email_errors.log", "a", encoding="utf-8") as f:
            f.write(f"--- Error at {datetime.now()} ---\n")
            f.write(f"Failed to send password reset email to {to_email}: {str(e)}\n\n")
            f.write(traceback.format_exc())
            f.write("\n----------------------------\n")
        return False

@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Handle password reset with token validation"""
    import hashlib
    
    if request.method == "POST":
        new_password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        if not new_password or not confirm_password:
            flash("Please fill in all fields.", "warning")
            return redirect(url_for('main.reset_password', token=token))
        
        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('main.reset_password', token=token))
        
        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return redirect(url_for('main.reset_password', token=token))
        
        # Verify token
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = get_db()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT user_id FROM password_reset_tokens 
                WHERE token = %s AND used = FALSE AND expires_at > NOW()
            """, (token_hash,))
            reset_token = cursor.fetchone()
            
            if not reset_token:
                flash("Invalid or expired reset link. Please request a new password reset.", "danger")
                return redirect(url_for('main.forgot_password'))
            
            # Update password (in production, use proper password hashing!)
            cursor.execute("""
                UPDATE users SET password = %s WHERE id = %s
            """, (new_password, reset_token['user_id']))
            
            # Mark token as used
            cursor.execute("""
                UPDATE password_reset_tokens SET used = TRUE WHERE token = %s
            """, (token_hash,))
            
            conn.commit()
            flash("Your password has been reset successfully. You can now login with your new password.", "success")
            return redirect(url_for('main.login'))
            
        except Exception as e:
            import traceback
            with open("password_reset_errors.log", "a") as f:
                f.write(f"\n--- Error at {datetime.now()} ---\n")
                f.write(traceback.format_exc())
            flash("An error occurred. Please try again.", "danger")
            return redirect(url_for('main.forgot_password'))
        finally:
            cursor.close()
    
    # Verify token is valid for GET request
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT user_id FROM password_reset_tokens 
            WHERE token = %s AND used = FALSE AND expires_at > NOW()
        """, (token_hash,))
        reset_token = cursor.fetchone()
        cursor.close()
        
        if not reset_token:
            flash("Invalid or expired reset link. Please request a new password reset.", "danger")
            return redirect(url_for('main.forgot_password'))
    except:
        cursor.close()
        flash("An error occurred. Please try again.", "danger")
        return redirect(url_for('main.forgot_password'))
    
    return render_template("reset_password.html", token=token)

@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor = ensure_visitor_form_settings()

    if request.method == "POST":
        form_type = request.form.get("form_type")
        
        if form_type == "smtp":
            server = request.form.get("server")
            port = request.form.get("port")
            username = request.form.get("username")
            password = request.form.get("password")
            
            # Check if settings exist
            cursor.execute("SELECT id FROM smtp_settings LIMIT 1")
            existing = cursor.fetchone()
            
            if existing:
                cursor.execute("""
                    UPDATE smtp_settings 
                    SET server=%s, port=%s, username=%s, password=%s 
                    WHERE id=%s
                """, (server, port, username, password, existing['id']))
            else:
                cursor.execute("""
                    INSERT INTO smtp_settings (server, port, username, password) 
                    VALUES (%s, %s, %s, %s)
                """, (server, port, username, password))
            flash("SMTP settings updated successfully!", "success")
        
        elif form_type == "visitor_fields":
            # Update each field setting
            cursor.execute("SELECT field_key FROM visitor_form_settings")
            all_fields = cursor.fetchall()
            
            for field in all_fields:
                key = field['field_key']
                # Checkboxes: only present in form if checked
                is_req = 1 if request.form.get(f"req_{key}") == "on" else 0
                is_vis = 1 if request.form.get(f"vis_{key}") == "on" else 0
                
                # System fields that MUST be visible/required
                if key in ['visitor_name', 'phone', 'purpose', 'person_to_meet']:
                    is_req = 1
                    is_vis = 1

                cursor.execute("""
                    UPDATE visitor_form_settings 
                    SET is_required=%s, is_visible=%s 
                    WHERE field_key=%s
                """, (is_req, is_vis, key))
            flash("Visitor form field settings updated!", "success")



        conn.commit()
        return redirect(url_for('main.settings'))

    # Fetch both settings
    cursor.execute("SELECT * FROM smtp_settings LIMIT 1")
    smtp_settings = cursor.fetchone()
    
    cursor.execute("SELECT * FROM visitor_form_settings ORDER BY id")
    field_settings = cursor.fetchall()
    

    
    cursor.close()
    
    return render_template("settings.html", 
                         settings=smtp_settings, 

                         field_settings=field_settings)

@bp.route("/checkout/<int:id>")
@login_required
def checkout(id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get visitor info and shed assignment
    cursor.execute("SELECT visitor_name, email, company, shed_id FROM visitors WHERE id=%s", (id,))
    visitor = cursor.fetchone()
    
    if visitor:
        # Update visitor status
        cursor.execute("UPDATE visitors SET status='OUT', check_out=NOW() WHERE id=%s", (id,))
        
        # Release shed if assigned
        if visitor.get('shed_id'):
            cursor.execute("UPDATE sheds SET status='AVAILABLE', customer_name=NULL WHERE id=%s", (visitor['shed_id'],))
            
        conn.commit()
        flash(f"{visitor['visitor_name']} has been checked out.", "info")
        
        # Send checkout notification
        if visitor['email']:
            # Get local IP for the link
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            except Exception:
                ip = "127.0.0.1"
            finally:
                s.close()

            base_url = url_for('main.badge', id=id, _external=True)
            badge_url = base_url.replace('localhost', ip).replace('127.0.0.1', ip)
            
            visitor_code = f"VIS-{id:06d}"
            send_badge_email(visitor['email'], visitor['visitor_name'], visitor_code, badge_url, "Check-Out", visitor['company'])
            

            
        flash(f"Visitor {visitor['visitor_name']} checked out successfully.", "success")
    
    cursor.close()
    return redirect(request.referrer or url_for("main.index"))

@bp.route("/badge/<int:id>")
@login_required
def badge(id):
    # Dynamic IP detection for reliable mobile scanning
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = "127.0.0.1"
    finally:
        s.close()

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM visitors WHERE id=%s", (id,))
    visitor = cursor.fetchone()
    cursor.close()
    
    if not visitor:
        return "Visitor entry not found in records.", 404
        
    return render_template("badge.html", visitor=visitor, local_ip=local_ip)

@bp.route("/visitor/<int:id>")
@login_required
def view_visitor(id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # Join with groups if applicable
    cursor.execute("""
        SELECT v.*, g.name as group_name 
        FROM visitors v
        LEFT JOIN visitor_groups g ON v.group_id = g.id
        WHERE v.id=%s
    """, (id,))
    visitor = cursor.fetchone()
    cursor.close()
    
    if not visitor:
        flash("Visitor not found.", "danger")
        return redirect(url_for("main.logs"))
        
    return render_template("view_visitor.html", visitor=visitor)

@bp.route("/api/resend-badge/<int:id>", methods=["GET", "POST"])
@login_required
def resend_badge(id):
    """Allows admin to resend the digital badge email."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT visitor_name, email, company FROM visitors WHERE id=%s", (id,))
    visitor = cursor.fetchone()
    cursor.close()
    
    if not visitor or not visitor['email']:
        msg = "Visitor not found or email not provided."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'message': msg})
        flash(msg, "warning")
        return redirect(request.referrer or url_for("main.logs"))
        
    # Get local IP for the link
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ip = "127.0.0.1"
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        pass
    finally:
        s.close()

    base_url = url_for('main.badge', id=id, _external=True)
    badge_url = base_url.replace('localhost', ip).replace('127.0.0.1', ip)
    
    visitor_code = f"VIS-{id:06d}"
    try:
        send_badge_email(visitor['email'], visitor['visitor_name'], visitor_code, badge_url, "Check-In", visitor['company'])
        msg = f"Digital badge successfully resent to {visitor['email']}."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json or 'api' in request.path:
            return jsonify({'success': True, 'message': msg})
        flash(msg, "success")
    except Exception as e:
        msg = f"Failed to send email: {str(e)}"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'message': msg})
        flash(msg, "danger")
        
    return redirect(request.referrer or url_for("main.logs"))

@bp.route("/verify/<int:id>")
def verify_visitor(id):
    """Public route for QR code verification - no login required"""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM visitors WHERE id=%s", (id,))
    visitor = cursor.fetchone()
    cursor.close()
    
    if not visitor:
        return "Visitor not found.", 404
        
    return render_template("verify.html", visitor=visitor)

@bp.route("/self-checkout/<int:id>", methods=["POST"])
def self_checkout(id):
    """Publicly accessible checkout for visitors using their scanned badge."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get visitor info for email
    cursor.execute("SELECT visitor_name, email, company FROM visitors WHERE id=%s", (id,))
    visitor = cursor.fetchone()
    
    if visitor:
        cursor.execute("UPDATE visitors SET status='OUT', check_out=NOW() WHERE id=%s", (id,))
        conn.commit()
        
        # Send checkout notification
        if visitor['email']:
            # Get local IP for the link
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
            except Exception:
                ip = "127.0.0.1"
            finally:
                s.close()

            base_url = url_for('main.badge', id=id, _external=True)
            badge_url = base_url.replace('localhost', ip).replace('127.0.0.1', ip)
            
            visitor_code = f"VIS-{id:06d}"
            send_badge_email(visitor['email'], visitor['visitor_name'], visitor_code, badge_url, "Check-Out", visitor['company'])
            
        flash(f"Check-out successful! Thank you for your visit, {visitor['visitor_name']}.", "success")
    
    cursor.close()
    return redirect(url_for("main.verify_visitor", id=id))

@bp.route("/upload-qr", methods=["POST"])
@login_required
def upload_qr():
    visitor_id = request.form.get("visitor_id")
    qr_data = request.form.get("qr_data") # Base64 string
    
    if not visitor_id or not qr_data:
        return {"success": False, "message": "Missing data"}, 400
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE visitors SET custom_qr=%s WHERE id=%s", (qr_data, visitor_id))
    conn.commit()
    cursor.close()
    
    return {"success": True, "message": "QR Code uploaded successfully"}

# --- GROUPS & REGULARS ROUTES ---

@bp.route("/visitors/checkout/<int:id>", methods=["GET", "POST"])
@login_required
def manual_checkout(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE visitors SET status='OUT', check_out=NOW() WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    flash("Visitor checked out successfully.", "success")
    return redirect(request.referrer or url_for('main.groups'))

@bp.route("/groups")
@login_required
def groups():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch all groups with active member count
    cursor.execute("""
        SELECT g.*, 
               (SELECT COUNT(*) FROM regular_visitors r WHERE r.group_id = g.id) as member_count
        FROM visitor_groups g 
        ORDER BY g.name
    """)
    groups = cursor.fetchall()
    
    # Fetch regular visitors with advanced stats (Total visits, Last Visit, currently On-Site)
    # matching by PHONE number which is the unique identifier usually
    cursor.execute("""
        SELECT r.*, 
               g.name as group_name, 
               g.color as group_color,
               (SELECT COUNT(*) FROM visitors v WHERE v.phone = r.phone) as total_visits,
               (SELECT MAX(check_in) FROM visitors v WHERE v.phone = r.phone) as last_visit,
               (SELECT COUNT(*) FROM visitors v WHERE v.phone = r.phone AND v.status = 'IN') > 0 as is_on_site,
               (SELECT id FROM visitors v WHERE v.phone = r.phone AND v.status = 'IN' LIMIT 1) as active_visit_id
        FROM regular_visitors r 
        LEFT JOIN visitor_groups g ON r.group_id = g.id 
        ORDER BY r.visitor_name
    """)
    regulars = cursor.fetchall()
    
    cursor.close()
    return render_template("groups.html", groups=groups, regulars=regulars)

@bp.route("/groups/add", methods=["POST"])
@login_required
def add_group():
    name = request.form.get("name")
    description = request.form.get("description")
    color = request.form.get("color", "primary")
    
    if not name:
        flash("Group name is required.", "warning")
        return redirect(url_for("main.groups"))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if group name already exists (case-insensitive)
        cursor.execute("SELECT name FROM visitor_groups WHERE LOWER(name) = LOWER(%s)", (name,))
        existing_group = cursor.fetchone()
        
        if existing_group:
            flash(f"⚠️ Group '{existing_group['name']}' already exists! Please choose a different name.", "error")
            cursor.close()
            return redirect(url_for("main.groups"))
        
        # Insert new group
        cursor.execute("INSERT INTO visitor_groups (name, description, color) VALUES (%s, %s, %s)", (name, description, color))
        conn.commit()
        flash(f"✨ Group '{name}' created successfully!", "success")
    except Exception as e:
        flash(f"❌ Error creating group: {str(e)}", "danger")
    finally:
        cursor.close()
    
    return redirect(url_for("main.groups"))


@bp.route("/groups/delete/<int:id>", methods=["GET", "POST"])
@login_required
def delete_group(id):
    # Allow GET for now to support existing links, but prefer POST
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get group name before deleting
        cursor.execute("SELECT name FROM visitor_groups WHERE id=%s", (id,))
        group = cursor.fetchone()
        
        if not group:
            flash("❌ Group not found!", "error")
            cursor.close()
            return redirect(url_for("main.groups"))
        
        group_name = group['name']
        
        # 1. Ungroup members first (Set group_id to NULL)
        cursor.execute("UPDATE regular_visitors SET group_id = NULL WHERE group_id = %s", (id,))
        
        # 2. Delete the group
        cursor.execute("DELETE FROM visitor_groups WHERE id=%s", (id,))
        conn.commit()
        
        flash(f"🗑️ Group '{group_name}' deleted successfully. Members are now ungrouped.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ Error deleting group: {str(e)}", "danger")
    finally:
        cursor.close()
    
    return redirect(url_for("main.groups"))

@bp.route('/api/groups')
@login_required
def get_groups_api():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name FROM visitor_groups ORDER BY name")
        groups = cursor.fetchall()
        return jsonify(groups)
    except Exception as e:
        print(f"Error fetching groups API: {e}")
        return jsonify([]), 500
    finally:
        cursor.close()

@bp.route('/api/visitors/bulk-add-to-group', methods=['POST'])
@login_required
def bulk_add_to_group():
    data = request.get_json()
    visitor_ids = data.get('visitor_ids', [])
    group_id = data.get('group_id')
    
    if not visitor_ids or not group_id:
        return jsonify({'success': False, 'message': 'Invalid data'})
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        success_count = 0
        skipped_count = 0
        
        for vid in visitor_ids:
            # Fetch visitor details
            cursor.execute("SELECT * FROM visitors WHERE id = %s", (vid,))
            visitor = cursor.fetchone()
            
            if not visitor:
                continue
                
            # Check if already in regular_visitors (matching by phone)
            cursor.execute("SELECT id FROM regular_visitors WHERE phone = %s", (visitor['phone'],))
            existing = cursor.fetchone()
            
            if existing:
                skipped_count += 1
                continue
                
            # Insert into regular_visitors
           
            cursor.execute("""




                INSERT INTO regular_visitors (group_id, visitor_name, company, phone, email, default_purpose, default_host)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (group_id, visitor['visitor_name'], visitor['company'], visitor['phone'], visitor['email'], visitor['purpose'], visitor['person_to_meet']))
            success_count += 1
            
        conn.commit()
        return jsonify({
            'success': True, 
            'message': f'Successfully added {success_count} visitors. {skipped_count} were already members.'
        })
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()

@bp.route("/api/visitors")
@login_required
def api_visitors():
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    days = request.args.get('days', type=int)
    limit = request.args.get('limit', 100, type=int)
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        query = "SELECT * FROM visitors WHERE 1=1"
        params = []
        
        if search:
            query += " AND (visitor_name LIKE %s OR company LIKE %s OR purpose LIKE %s OR person_to_meet LIKE %s)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])
            
        if status:
            query += " AND status = %s"
            params.append(status)
            
        if days is not None:
            if days == 0:
                query += " AND DATE(check_in) = CURDATE()"
            elif days == 1:
                query += " AND DATE(check_in) = SUBDATE(CURDATE(), 1)"
            else:
                query += " AND check_in >= DATE(NOW()) - INTERVAL %s DAY"
                params.append(days)
                
        query += " ORDER BY check_in DESC LIMIT %s"
        params.append(limit)
        
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        
        # Convert datetime objects to strings for JSON
        for r in results:
            if r['check_in']: r['check_in'] = r['check_in'].isoformat()
            if r['check_out']: r['check_out'] = r['check_out'].isoformat()
            
        return jsonify(results)
    except Exception as e:
        print(f"API Error fetching visitors: {e}")
        return jsonify([]), 500
    finally:
        cursor.close()



@bp.route("/api/visitor-history")
@login_required
def visitor_history():
    phone = request.args.get('phone')
    if not phone:
        return jsonify([])
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT visitor_name, company, purpose, person_to_meet, check_in, check_out, status, id
        FROM visitors 
        WHERE phone = %s 
        ORDER BY check_in DESC 
        LIMIT 10
    """, (phone,))
    history = cursor.fetchall()
    cursor.close()
    
    return jsonify(history)

@bp.route("/api/members/bulk-update", methods=["POST"])
@login_required
def bulk_update_members():
    data = request.json
    ids = data.get('ids', [])
    action = data.get('action') # 'set_group', 'ungroup', 'delete'
    group_id = data.get('group_id')
    
    if not ids or not action:
        return jsonify({"success": False, "message": "Missing data"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        if action == 'delete':
            # Create placeholder for ids
            placeholders = ', '.join(['%s'] * len(ids))
            
            # 1. Unlink from history first (Constraint Safety)
            cursor.execute(f"UPDATE visitors SET regular_visitor_id = NULL WHERE regular_visitor_id IN ({placeholders})", ids)
            
            # 2. Now delete the regular member
            cursor.execute(f"DELETE FROM regular_visitors WHERE id IN ({placeholders})", ids)
            deleted_count = cursor.rowcount
            if deleted_count == 0:
                 raise Exception("Database reported 0 rows deleted. IDs might get mismatch.")
            
            msg = f"Successfully deleted {deleted_count} members."
            
        elif action == 'ungroup':
            placeholders = ', '.join(['%s'] * len(ids))
            cursor.execute(f"UPDATE regular_visitors SET group_id = NULL WHERE id IN ({placeholders})", ids)
            msg = f"Removed {len(ids)} members from their group."
            
        elif action == 'set_group':
            placeholders = ', '.join(['%s'] * len(ids))
            # Append group_id to the params. Params structure: (group_id, id1, id2, ...)
            params = [group_id] + ids
            cursor.execute(f"UPDATE regular_visitors SET group_id = %s WHERE id IN ({placeholders})", params)
            msg = f"Moved {len(ids)} members to new group."
            
        conn.commit()
        print(f"--- BULK UPDATE SUCCESS: {action} on {len(ids)} items ---")
        flash(msg, "success")
        return jsonify({"success": True, "message": msg})
        
    except Exception as e:
        conn.rollback()
        print(f"--- BULK UPDATE ERROR: {str(e)} ---")
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()

@bp.route("/regulars/delete/<int:id>", methods=["GET", "POST"])
@login_required
def delete_regular(id):
    print(f"--- ATTEMPTING DELETE REGULAR ID: {id} ---")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM regular_visitors WHERE id = %s", (id,))
        rows_deleted = cursor.rowcount
        conn.commit()
        print(f"--- DELETED {rows_deleted} ROWS ---")
        if rows_deleted == 0:
            flash("Member not found or already deleted.", "warning")
        else:
            flash("Member removed successfully.", "success")
    except Exception as e:
        conn.rollback()
        print(f"--- DELETE ERROR: {e} ---")
        flash(f"Error removing member: {str(e)}", "danger")
    finally:
        cursor.close()
    return redirect(url_for('main.groups'))

@bp.route("/regulars/update/<int:id>", methods=["POST"])
@login_required
def update_regular(id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        visitor_name = request.form.get('visitor_name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        company = request.form.get('company')
        default_purpose = request.form.get('default_purpose')
        default_host = request.form.get('default_host')
        
        cursor.execute("""
            UPDATE regular_visitors 
            SET visitor_name=%s, phone=%s, email=%s, company=%s, default_purpose=%s, default_host=%s
            WHERE id=%s
        """, (visitor_name, phone, email, company, default_purpose, default_host, id))
        conn.commit()
        flash("Member details updated successfully.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error updating member: {e}", "danger")
    finally:
        cursor.close()
    return redirect(url_for('main.groups'))

@bp.route("/api/search-visitors")
@login_required
def search_visitors_api():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    search_term = f"%{query}%"
    try:
        # Fetch all matches ordered by latest check-in
        # We handle deduplication in Python to ensure we get the LATEST details for each phone
        is_numeric = query.isdigit()
        sql_base = """
            SELECT visitor_name, phone, company, email, person_to_meet, purpose 
            FROM visitors 
            WHERE visitor_name LIKE %s OR phone LIKE %s
        """
        params = [search_term, search_term]
        
        if is_numeric:
            sql_base += " OR id = %s"
            params.append(query)
            
        sql_base += " ORDER BY check_in DESC LIMIT 100"
        
        cursor.execute(sql_base, tuple(params))
        raw_results = cursor.fetchall()
        
        # Smart Aggregation: Deduplicate by phone, but backfill missing info from older records
        visitors_map = {}
        ordered_phones = [] # To preserve order of latest check-in
        
        for row in raw_results:
            phone = row.get('phone')
            if not phone: continue
            
            if phone not in visitors_map:
                visitors_map[phone] = row.copy()
                ordered_phones.append(phone)
            else:
                # If the latest record has missing fields, try to fill from older history
                current = visitors_map[phone]
                if not current.get('company') and row.get('company'):
                    current['company'] = row['company']
                if not current.get('person_to_meet') and row.get('person_to_meet'):
                    current['person_to_meet'] = row['person_to_meet']
                if not current.get('purpose') and row.get('purpose'):
                    current['purpose'] = row['purpose']
                if not current.get('email') and row.get('email'):
                    current['email'] = row['email']
        
        # Construct final list in order
        unique_results = []
        for p in ordered_phones:
            unique_results.append(visitors_map[p])
            if len(unique_results) >= 10:
                break
                    
        return jsonify(unique_results)
    except Exception as e:
        print(f"Search API Error: {e}")
        return jsonify([])
    finally:
        cursor.close()




@bp.route("/regulars/add", methods=["POST"])
@login_required
def add_regular():
    import traceback
    try:
        name = request.form.get("visitor_name")
        group_id = request.form.get("group_id")
        company = request.form.get("company")
        phone = request.form.get("phone")
        email = request.form.get("email")
        purpose = request.form.get("purpose")
        host = request.form.get("person_to_meet")
        
        if not name or not phone:
             flash("Name and Phone are required.", "warning")
             return redirect(url_for("main.groups"))

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # Check for duplicate phone
        cursor.execute("""
            SELECT r.id, r.visitor_name, g.name as group_name 
            FROM regular_visitors r 
            LEFT JOIN visitor_groups g ON r.group_id = g.id 
            WHERE r.phone = %s
        """, (phone,))
        existing_member = cursor.fetchone()
        
        if existing_member:
            # STOP: Do not add or move.
            current_group = existing_member['group_name'] or "Ungrouped"
            flash(f"⚠️ Action Blocked: Member '{existing_member['visitor_name']}' is already in the '{current_group}' group.", "warning")
        else:
            # INSERT new member
            cursor.execute("""
                INSERT INTO regular_visitors 
                (group_id, visitor_name, company, phone, email, default_purpose, default_host)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (group_id if group_id else None, name, company, phone, email, purpose, host))
            conn.commit()
            flash(f"✨ Successfully added '{name}' to the group.", "success")
            
        cursor.close()
    except Exception as e:
        flash(f"Error processing visitor: {str(e)}", "danger")
        print(traceback.format_exc())
        
    return redirect(url_for("main.groups"))

@bp.route("/regulars/edit/<int:id>", methods=["POST"])
@login_required
def edit_regular(id):
    try:
        name = request.form.get("visitor_name")
        group_id = request.form.get("group_id")
        company = request.form.get("company")
        phone = request.form.get("phone")
        email = request.form.get("email")
        purpose = request.form.get("purpose")
        host = request.form.get("person_to_meet")
        
        if not name or not phone:
             flash("Name and Phone are required.", "warning")
             return redirect(url_for("main.groups"))

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE regular_visitors 
            SET group_id=%s, visitor_name=%s, company=%s, phone=%s, email=%s, default_purpose=%s, default_host=%s
            WHERE id=%s
        """, (group_id if group_id else None, name, company, phone, email, purpose, host, id))
        conn.commit()
        cursor.close()
        flash(f"Regular visitor '{name}' updated.", "success")
    except Exception as e:
        flash(f"Error updating regular visitor: {str(e)}", "danger")
        
    return redirect(url_for("main.groups"))




@bp.route("/regulars/checkin/<int:id>")
@login_required
def checkin_regular(id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get regular details
    cursor.execute("SELECT * FROM regular_visitors WHERE id=%s", (id,))
    regular = cursor.fetchone()
    cursor.close()
    
    if not regular:
        flash("Regular visitor not found.", "danger")
        return redirect(url_for("main.groups"))
        
    # Redirect to add_visitor with query params
    import urllib.parse
    params = {
        'visitor_name': regular['visitor_name'],
        'company': regular['company'] or '',
        'phone': regular['phone'],
        'email': regular['email'] or '',
        'purpose': regular['default_purpose'] or '',
        'person_to_meet': regular['default_host'] or '',
        'group_id': regular['group_id'] or '',
        'regular_id': regular['id']
    }
    
    # Remove empty params to avoid url clutter
    params = {k: v for k, v in params.items() if v}
    
    # Construct query string
    query_string = urllib.parse.urlencode(params)
    return redirect(url_for('main.add_visitor') + '?' + query_string)

# --- USER PROFILE ROUTES ---

@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """User profile page where users can view and update their information"""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        user_id = session['user_id']
        
        try:
            cursor.execute("""
                UPDATE users 
                SET full_name = %s, email = %s 
                WHERE id = %s
            """, (full_name, email, user_id))
            conn.commit()
            
            flash("Profile updated successfully!", "success")
            return redirect(url_for('main.profile'))
        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "danger")
        finally:
            cursor.close()
    
    # GET request - fetch user data
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.close()
        
        if not user:
            flash("User not found", "danger")
            return redirect(url_for('main.logout'))
        
        return render_template("profile.html", user=user)
    except Exception as e:
        flash(f"Error loading profile: {str(e)}", "danger")
        return redirect(url_for('main.index'))



@bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    """Change user password"""
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        flash("All fields are required", "warning")
        return redirect(url_for('main.profile'))
    
    if new_password != confirm_password:
        flash("New passwords do not match", "danger")
        return redirect(url_for('main.profile'))
    
    if len(new_password) < 6:
        flash("Password must be at least 6 characters long", "warning")
        return redirect(url_for('main.profile'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Verify current password
        cursor.execute("SELECT password FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        
        if not user or user['password'] != current_password:
            flash("Current password is incorrect", "danger")
            return redirect(url_for('main.profile'))
        
        # Update password
        cursor.execute("""
            UPDATE users 
            SET password = %s 
            WHERE id = %s
        """, (new_password, session['user_id']))
        conn.commit()
        
        flash("Password changed successfully!", "success")
        return redirect(url_for('main.profile'))
    except Exception as e:
        flash(f"Error changing password: {str(e)}", "danger")
        return redirect(url_for('main.profile'))
    finally:
        cursor.close()

# --- USER MANAGEMENT ROUTES (ADMIN ONLY) ---

@bp.route("/user-management", methods=["GET"])
@bp.route("/users", methods=["GET"])
@login_required
def user_management():
    """User management page - only accessible by admins"""
    # Check if user is admin
    if session.get('role') != 'ADMIN':
        flash("Access denied. Only administrators can access user management.", "danger")
        return redirect(url_for('main.index'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get pending users
        cursor.execute("""
            SELECT id, full_name, username, email, role, created_at
            FROM users 
            WHERE status = 'PENDING'
            ORDER BY id DESC
        """)
        pending_users = cursor.fetchall()
        
        # Get approved users
        cursor.execute("""
            SELECT u.id, u.full_name, u.username, u.email, u.role, u.created_at, u.approved_at,
                   approver.username as approved_by_name
            FROM users u
            LEFT JOIN users approver ON u.approved_by = approver.id
            WHERE u.status = 'APPROVED'
            ORDER BY u.id DESC
        """)
        approved_users = cursor.fetchall()
        
        # Get rejected/deactivated users
        cursor.execute("""
            SELECT id, full_name, username, email, role, created_at, approved_at
            FROM users 
            WHERE status = 'REJECTED'
            ORDER BY id DESC
        """)
        rejected_users = cursor.fetchall()
        
        return render_template("user_management.html", 
                             pending_users=pending_users,
                             approved_users=approved_users,
                             rejected_users=rejected_users)
    finally:
        cursor.close()

@bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
def approve_user(user_id):
    """Approve or reject a user"""
    # Check if user is admin
    if session.get('role') != 'ADMIN':
        flash("Access denied. Only administrators can approve users.", "danger")
        return redirect(url_for('main.index'))
    
    action = request.form.get('action')  # 'approve' or 'reject'
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        if action == 'approve':
            cursor.execute("""
                UPDATE users 
                SET status = 'APPROVED', 
                    approved_by = %s, 
                    approved_at = NOW()
                WHERE id = %s
            """, (session['user_id'], user_id))
            flash("User approved successfully!", "success")
        elif action == 'reject':
            cursor.execute("""
                UPDATE users 
                SET status = 'REJECTED', 
                    approved_by = %s, 
                    approved_at = NOW()
                WHERE id = %s
            """, (session['user_id'], user_id))
            flash("User rejected.", "info")
        
        conn.commit()
    except Exception as e:
        flash(f"Error processing request: {str(e)}", "danger")
    finally:
        cursor.close()
    
    return redirect(url_for('main.user_management'))

@bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user(user_id):
    """Deactivate an approved user"""
    # Check if user is admin
    if session.get('role') != 'ADMIN':
        flash("Access denied. Only administrators can deactivate users.", "danger")
        return redirect(url_for('main.index'))
    
    # Prevent self-deactivation
    if user_id == session.get('user_id'):
        flash("You cannot deactivate your own account.", "warning")
        return redirect(url_for('main.user_management'))
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE users 
            SET status = 'REJECTED'
            WHERE id = %s
        """, (user_id,))
        conn.commit()
        flash("User deactivated successfully.", "success")
    except Exception as e:
        flash(f"Error deactivating user: {str(e)}", "danger")
    finally:
        cursor.close()
    
    return redirect(url_for('main.user_management'))

# --- DRAFT MANAGEMENT ROUTES ---
@bp.route("/draft/delete/<int:draft_id>", methods=["POST"])
@login_required
def delete_draft(draft_id):
    """Delete a draft visitor entry"""
    print(f"🗑️ DEBUG: Attempting to delete draft ID: {draft_id}")
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Check if the record exists first
        cursor.execute("SELECT id, visitor_name FROM visitors WHERE id = %s AND is_draft = 1", (draft_id,))
        target = cursor.fetchone()
        
        if not target:
            print(f"⚠️ DEBUG: No draft found with ID {draft_id} that is marked as is_draft=1")
            flash("Draft not found or already processed.", "warning")
        else:
            print(f"✅ DEBUG: Found draft '{target[1]}' (ID: {draft_id}). Proceeding with deletion.")
            cursor.execute("DELETE FROM visitors WHERE id = %s AND is_draft = 1", (draft_id,))
            conn.commit()
            print(f"✨ DEBUG: Successfully deleted {cursor.rowcount} rows.")
            flash(f"Draft for '{target[1]}' discarded successfully.", "success")
            
    except Exception as e:
        print(f"❌ DEBUG ERROR: Exception during draft deletion: {str(e)}")
        flash(f"Error discarding draft: {str(e)}", "danger")
    finally:
        cursor.close()
    
    return redirect(url_for('main.add_visitor'))


@bp.route("/drafts", methods=["GET"])
@login_required
def draft_list():
    """View all pending drafts"""
    print("🔍 DEBUG: draft_list route called")
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT v.*, u.username as created_by_name 
            FROM visitors v 
            LEFT JOIN users u ON v.draft_created_by = u.id
            WHERE v.is_draft = 1 
            ORDER BY v.draft_created_at DESC
        """)
        drafts = cursor.fetchall()
        print(f"🔍 DEBUG: Found {len(drafts)} drafts")
    except Exception as e:
        print(f"Error fetching drafts: {e}")
        drafts = []
    finally:
        cursor.close()
    
    return render_template("draft_list.html", drafts=drafts)


@bp.route("/draft/activate/<int:draft_id>", methods=["POST"])
@login_required
def activate_draft(draft_id):
    """Activate a draft and generate badge immediately"""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Fetch the draft
        cursor.execute("SELECT * FROM visitors WHERE id = %s AND is_draft = 1", (draft_id,))
        draft = cursor.fetchone()
        
        if not draft:
            flash("Draft not found or already activated.", "warning")
            return redirect(url_for('main.draft_list'))
        
        # Check if required fields are filled
        if not draft['visitor_name'] or not draft['phone'] or not draft['person_to_meet']:
            flash("Cannot activate draft: Missing required fields (name, phone, host). Please edit the draft first.", "warning")
            return redirect(url_for('main.add_visitor', draft_id=draft_id))
        
        # Activate the draft
        cursor.execute("""
            UPDATE visitors SET
            status = 'IN', 
            check_in = NOW(), 
            is_draft = 0
            WHERE id = %s AND is_draft = 1
        """, (draft_id,))
        conn.commit()
        
        # Send badge email if email provided
        if draft['email']:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # doesn't even have to be reachable
                s.connect(('10.255.255.255', 1))
                local_ip = s.getsockname()[0]
            except Exception:
                local_ip = '127.0.0.1'
            finally:
                s.close()

            base_url = url_for('main.badge', id=draft_id, _external=True)
            badge_url = base_url.replace('localhost', local_ip).replace('127.0.0.1', local_ip)
            visitor_code = f"VIS-{draft_id:06d}"
            send_badge_email(draft['email'], draft['visitor_name'], visitor_code, badge_url, "Check-In", draft['company'])
        
        flash(f"Draft activated! Badge generated for {draft['visitor_name']}.", "success")
        return redirect(url_for("main.badge", id=draft_id))
        
    except Exception as e:
        flash(f"Error activating draft: {str(e)}", "danger")
        return redirect(url_for('main.draft_list'))
    finally:
        cursor.close()

@bp.route("/coe")
@bp.route("/admin/coe")
@bp.route("/logistics")
@login_required
def coe():
    try:
        if session.get('role') != 'ADMIN':
            flash("Access denied.", "danger")
            return redirect(url_for('main.index'))
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Fetch Sheds & Group by Customer
        cursor.execute("SELECT * FROM sheds ORDER BY customer_name, name")
        sheds_raw = cursor.fetchall()
        
        cursor.execute("SELECT * FROM meeting_rooms ORDER BY name")
        rooms_raw = cursor.fetchall()
        
        # Build Customer-wise Shed Hierarchy
        customers = {}
        for s in sheds_raw:
            cust = s['customer_name'] or "General/Unassigned"
            if cust not in customers:
                customers[cust] = {'name': cust, 'sheds': []}
            
            # Attach rooms to this shed
            s['facilities'] = [r for r in rooms_raw if r['shed_id'] == s['id']]
            customers[cust]['sheds'].append(s)
            
        customer_list = list(customers.values())

        # 2. Fetch Unallocated Visitors (At Security Gate)
        cursor.execute("""
            SELECT id, visitor_name, company, check_in, phone, purpose
            FROM visitors
            WHERE status = 'IN' AND shed_id IS NULL
            ORDER BY check_in DESC
        """)
        unallocated = cursor.fetchall()
        
        # 3. Fetch Live Occupancy (Allocated)
        cursor.execute("""
            SELECT v.id, v.visitor_name, v.company, s.name as shed_name, s.customer_name
            FROM visitors v
            JOIN sheds s ON v.shed_id = s.id
            WHERE v.status = 'IN'
            ORDER BY v.check_in DESC
        """)
        allocated = cursor.fetchall()
        
        # Stats
        stats = {
            'total_sheds': len(sheds_raw),
            'active_customers': len(customers),
            'waiting': len(unallocated),
            'on_site': len(allocated)
        }

        return render_template("CoE.html", 
                             customers=customer_list, 
                             unallocated=unallocated, 
                             allocated=allocated, 
                             stats=stats)
    except Exception as e:
        print(f"Error in coe redesign: {str(e)}")
        flash(f"Error loading CoE: {str(e)}", "danger")
        return redirect(url_for('main.index'))

@bp.route("/api/coe/allocate", methods=["POST"])
@login_required
def coe_allocate():
    if session.get('role') != 'ADMIN':
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.json
    visitor_id = data.get('visitor_id')
    shed_id = data.get('shed_id')
    
    if not visitor_id or not shed_id:
        return jsonify({"success": False, "error": "Missing data"}), 400
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE visitors SET shed_id = %s WHERE id = %s", (shed_id, visitor_id))
        conn.commit()
        cursor.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        print(f"Error in coe: {str(e)}")
        flash(f"Error loading CoE: {str(e)}", "danger")
        return redirect(url_for('main.index'))

@bp.route("/api/shed/detail/<int:shed_id>")
@login_required
def api_shed_detail(shed_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM sheds WHERE id = %s", (shed_id,))
    shed = cursor.fetchone()
    cursor.close()
    if shed:
        return jsonify(shed)
    return jsonify({"error": "Shed not found"}), 404

@bp.route("/api/asset/get/<int:asset_id>")
@login_required
def api_asset_get(asset_id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM meeting_rooms WHERE id = %s", (asset_id,))
    asset = cursor.fetchone()
    cursor.close()
    if asset:
        return jsonify(asset)
    return jsonify({"error": "Asset not found"}), 404

@bp.route("/api/asset/register", methods=["POST"])
@login_required
def api_asset_register():
    if session.get('role') != 'ADMIN':
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.json
    name = data.get('name')
    type = data.get('type')
    shed_id = data.get('shed_id')
    
    if not name or not type or not shed_id:
        return jsonify({"success": False, "error": "Missing fields"}), 400
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO meeting_rooms (name, type, shed_id, status) VALUES (%s, %s, %s, 'AVAILABLE')", (name, type, shed_id))
        conn.commit()
        cursor.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
        floor_count = len([r for r in rooms_flat if r.get('type') == 'SHOPFLOOR'])

        cursor.close()
        return render_template("logistics.html", 
                             sheds=hierarchical_sheds, 
                             rooms=rooms_flat, 
                             occupancy=occupancy,
                             shed_stats=shed_stats,
                             room_stats=room_stats,
                             room_count=room_count,
                             conf_count=conf_count,
                             floor_count=floor_count)
    except Exception as e:
        import traceback
        with open("logistics_error.log", "a") as f:
            f.write(f"\n--- Error at {datetime.now()} ---\n")
            f.write(traceback.format_exc())
        return f"Logistics Error: {str(e)}", 500

@bp.route("/api/shed/update", methods=["POST"])
@login_required
def update_shed():
    data = request.json
    shed_id = data.get('id')
    status = data.get('status')
    customer = data.get('customer')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE sheds SET status=%s, customer_name=%s WHERE id=%s", (status, customer, shed_id))
    conn.commit()
    cursor.close()
    return jsonify({"success": True})

@bp.route("/api/room/update", methods=["POST"])
@login_required
def update_room():
    data = request.json
    room_id = data.get('id')
    status = data.get('status')
    reason = data.get('reason')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE meeting_rooms SET status=%s, blocked_reason=%s WHERE id=%s", (status, reason, room_id))
    conn.commit()
    cursor.close()
    return jsonify({"success": True})

@bp.route("/api/asset/register", methods=["POST"])
@login_required
def register_asset():
    data = request.json
    name = data.get('name')
    type = data.get('type')
    shed_id = data.get('shed_id')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO meeting_rooms (name, type, shed_id, status) VALUES (%s, %s, %s, 'AVAILABLE')", 
                   (name, type, shed_id))
    conn.commit()
    cursor.close()
    return jsonify({"success": True})

@bp.route("/api/asset/delete", methods=["POST"])
@login_required
def delete_asset():
    data = request.json
    asset_id = data.get('id')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meeting_rooms WHERE id=%s", (asset_id,))
    conn.commit()
    cursor.close()
    return jsonify({"success": True})

@bp.route("/api/asset/get/<int:id>")
@login_required
def get_asset(id):
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM meeting_rooms WHERE id=%s", (id,))
    asset = cursor.fetchone()
    cursor.close()
    return jsonify(asset)

# --- DMT ROUTES ---

@bp.route('/dmt')
@login_required
def dmt():
    return render_template('dmt.html')

@bp.route('/dmt/import', methods=['POST'])
@login_required
def dmt_import():
    file = request.files.get('import_file')
    import_type = request.form.get('import_type')
    # For demo: just show CSV headers/rows as preview
    if not file:
        return jsonify({'preview_html': '<div class="alert alert-danger">No file uploaded.</div>'})
    try:
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.reader(stream)
        rows = list(reader)
        preview_html = '<table class="table table-bordered"><thead><tr>'
        for col in rows[0]:
            preview_html += f'<th>{col}</th>'
        preview_html += '</tr></thead><tbody>'
        for row in rows[1:6]:
            preview_html += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
        preview_html += '</tbody></table>'
        return jsonify({'preview_html': preview_html})
    except Exception as e:
        return jsonify({'preview_html': f'<div class="alert alert-danger">Error: {e}</div>'})

@bp.route('/dmt/export/<datatype>')
@login_required
def dmt_export(datatype):
    # Dummy export: returns a CSV with headers only
    output = io.StringIO()
    writer = csv.writer(output)
    if datatype == 'visitors':
        writer.writerow(['id', 'name', 'company', 'status'])
    elif datatype == 'groups':
        writer.writerow(['id', 'name'])
    elif datatype == 'assets':
        writer.writerow(['id', 'name', 'type', 'status'])
    else:
        writer.writerow(['unknown'])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype='text/csv', as_attachment=True, download_name=f'{datatype}.csv')

@bp.route('/dmt/template/<datatype>')
@login_required
def dmt_template(datatype):
    wb = Workbook()
    ws = wb.active
    if datatype == 'visitors':
        ws.append(['id', 'name', 'company', 'status'])
    elif datatype == 'groups':
        ws.append(['id', 'name'])
    elif datatype == 'assets':
        ws.append(['id', 'name', 'type', 'status'])
    else:
        ws.append(['unknown'])
    from io import BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f'{datatype}_template.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@bp.route('/menu-maintenance')
@login_required
def menu_maintenance():
    return render_template('menu_maintenance.html')

# Cache for sidebar menu to prevent DB hits on every single page render
SIDEBAR_MENU_CACHE = None

@bp.context_processor
def inject_sidebar_menu():
    """Inject menu items into templates."""
    global SIDEBAR_MENU_CACHE
    try:
        # Avoid connecting to DB on every request if we already have the menu cached
        if SIDEBAR_MENU_CACHE is None:
            conn = get_db()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM sidebar_menu ORDER BY ordering")
            SIDEBAR_MENU_CACHE = cursor.fetchall()
        
        all_items = SIDEBAR_MENU_CACHE
        
        # Restrict menus for Security role
        role = session.get('role', '')
        if role == 'SECURITY':
            allowed_menus = ['dashboard', 'logs', 'add'] # Grant as needed
            items = [item for item in all_items if item['name'] in allowed_menus]
        else:
            items = all_items
            
    except Exception as e:
        print(f"Error loading sidebar menu: {e}")
        items = []
    return dict(sidebar_menu_items=items)

@bp.route('/api/sidebar-menu', methods=['GET'])
@login_required
def api_get_sidebar_menu():
    """Fetch all sidebar menu items for the maintenance page."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, label, icon, url, ordering, enabled FROM sidebar_menu ORDER BY ordering")
    items = cursor.fetchall()
    cursor.close()
    return jsonify(items)

@bp.route('/api/sidebar-menu/<int:item_id>/toggle', methods=['POST'])
@login_required
def api_toggle_sidebar_menu(item_id):
    """Toggle the enabled status of a sidebar menu item with extreme logging."""
    try:
        # 1. Auth Check
        user_role = str(session.get('role', '')).upper()
        if user_role != 'ADMIN':
            print(f"[TOGGLE_LOG] Access Blocked: {session.get('username')} is {user_role}")
            return jsonify({'success': False, 'error': f'Admin role required (You are: {user_role})'}), 403

        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        
        # 2. Get current state
        cursor.execute("SELECT id, name, label, enabled FROM sidebar_menu WHERE id = %s", (item_id,))
        row = cursor.fetchone()
        
        if not row:
            print(f"[TOGGLE_LOG] ID {item_id} not found")
            cursor.close()
            return jsonify({'success': False, 'error': 'Item not found'}), 404
            
        # 3. Explicitly detect state (handling boolean, int, or bytes)
        raw_val = row['enabled']
        is_currently_on = bool(raw_val) # Python treats 1, True, b'\x01' as True
        new_state = 0 if is_currently_on else 1
        
        print(f"[TOGGLE_LOG] ID:{item_id} ({row['label']}) | RawDB:{raw_val} | Detected:{is_currently_on} | Target:{new_state}")
        
        # 4. Perform Update
        cursor.execute("UPDATE sidebar_menu SET enabled = %s WHERE id = %s", (new_state, item_id))
        conn.commit()
        
        # 5. Verify
        cursor.execute("SELECT enabled FROM sidebar_menu WHERE id = %s", (item_id,))
        final_row = cursor.fetchone()
        final_val = bool(final_row['enabled'])
        
        print(f"[TOGGLE_LOG] UPDATED Successfully. Final State: {final_val}")
        
        cursor.close()
        return jsonify({
            'success': True,
            'enabled': final_val,
            'label': row['label']
        })

    except Exception as e:
        print(f"[TOGGLE_LOG] CRITICAL ERROR: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/sidebar-menu/reset', methods=['POST'])
@login_required
def api_reset_sidebar_menu():
    """Emergency: Force enable all menu items."""
    if str(session.get('role', '')).upper() != 'ADMIN':
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE sidebar_menu SET enabled = 1")
        conn.commit()
        cursor.close()
        return jsonify({'success': True, 'message': 'All modules enabled'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def send_department_alert_email(to_email, visitor_name, company, purpose, person_to_meet):
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM smtp_settings WHERE status = 1 LIMIT 1")
        settings = cursor.fetchone()
        cursor.close()

        if not settings:
            print(f"No SMTP settings configured. Alert email to {to_email} simulated.")
            return False

        SMTP_SERVER = settings['server']
        SMTP_PORT = settings['port']
        SMTP_USER = settings['username']
        SMTP_PASS = settings['password']

        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Action Required: New Customer Visit - {visitor_name}"

        body = f"""
        A new customer visit has been scheduled.
        Visitor: {visitor_name}
        Company: {company}
        Purpose: {purpose}
        Host: {person_to_meet}

        Please log into the Visitor Portal and review the Projects Logistics panel to enter pickup/drop details if required.
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send department alert email: {e}")
        return False

def send_host_approval_email(host_name, visitor_name, visitor_id):
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        import urllib.parse
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM smtp_settings WHERE status = 1 LIMIT 1")
        settings = cursor.fetchone()
        
        # Look up host email by full name
        cursor.execute("SELECT email FROM users WHERE full_name = %s LIMIT 1", (host_name,))
        host_user = cursor.fetchone()
        cursor.close()

        if not host_user or not host_user.get('email'):
            print(f"Host {host_name} not found or has no email.")
            return False
            
        to_email = host_user['email']
        
        if not settings:
            print(f"No SMTP settings. Host approval email to {to_email} simulated.")
            return False

        SMTP_SERVER = settings['server']
        SMTP_PORT = settings['port']
        SMTP_USER = settings['username']
        SMTP_PASS = settings['password']

        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Approval Required: Logistics Arranged for Visitor {visitor_name}"

        approval_link = url_for('main.approve_visitor_logistics', visitor_id=visitor_id, _external=True)

        body = f"""
        Logistics (pickup/drop details) have been arranged for your visitor: {visitor_name}.
        
        Please click the link below to approve:
        {approval_link}
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send host approval email: {e}")
        return False

@bp.route('/api/quick_visitors', methods=['GET'])
@login_required
def api_quick_visitors():
    q = request.args.get('q', '')
    status = request.args.get('status', '')
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        query = "SELECT id, visitor_name, company, person_to_meet, phone, status FROM visitors WHERE (visitor_name LIKE %s OR phone LIKE %s OR id LIKE %s)"
        params = [f"%{q}%", f"%{q}%", f"%{q}%"]
        if status:
            query += " AND status = %s"
            params.append(status)
        query += " LIMIT 10"
        cursor.execute(query, tuple(params))
        results = cursor.fetchall()
        cursor.close()
        return jsonify(results)
    except Exception as e:
        print(f"API Visitors Error: {e}")
        return jsonify([])

@bp.route('/api/request_deletion/<int:visitor_id>', methods=['POST'])
@login_required
def request_deletion(visitor_id):
    if session.get('role') not in ['SECURITY', 'ADMIN', 'MANAGEMENT']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE visitors SET deletion_requested = 1 WHERE id = %s", (visitor_id,))
        conn.commit()
        
        # ADD SECURITY ALERT
        cursor.execute("SELECT visitor_name FROM visitors WHERE id = %s", (visitor_id,))
        v_name = cursor.fetchone()['visitor_name']
        add_security_alert(
            'WARNING', 
            'Deletion Requested', 
            f'Security/User has requested deletion of visitor {v_name} data. Admin approval required.', 
            visitor_id, 
            url_for('main.logs')
        )

        cursor.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/api/approve_deletion/<int:visitor_id>', methods=['POST'])
@login_required
def approve_deletion(visitor_id):
    if session.get('role') not in ['ADMIN', 'MANAGEMENT']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM visitors WHERE id = %s", (visitor_id,))
        conn.commit()
        cursor.close()
        flash('Visitor data deleted successfully.', 'success')
        return redirect(url_for('main.logs'))
    except Exception as e:
        flash(f'Error deleting data: {e}', 'error')
        return redirect(url_for('main.logs'))

@bp.route('/api/reject_deletion/<int:visitor_id>', methods=['POST'])
@login_required
def reject_deletion(visitor_id):
    if session.get('role') not in ['ADMIN', 'MANAGEMENT']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE visitors SET deletion_requested = 0 WHERE id = %s", (visitor_id,))
        conn.commit()
        cursor.close()
        flash('Deletion request rejected.', 'info')
        return redirect(url_for('main.logs'))
    except Exception as e:
        flash(f'Error rejecting deletion: {e}', 'error')
        return redirect(url_for('main.logs'))

@bp.route('/projects-logistics', methods=['GET', 'POST'])
@login_required
def projects_logistics():
    role = session.get('role', '').upper()
    
    if request.method == 'POST':
        if role == 'ADMIN':
            flash("Administrators can only view these details. The Projects team must allocate it.", "warning")
            return redirect(url_for('main.projects_logistics'))
        
        visitor_id = request.form.get('visitor_id')
        pickup_details = request.form.get('pickup_details')
        drop_details = request.form.get('drop_details')
        
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("UPDATE visitors SET pickup_details = %s, drop_details = %s WHERE id = %s", (pickup_details, drop_details, visitor_id))
        conn.commit()
        
        # Get visitor info to alert the host
        cursor.execute("SELECT person_to_meet, visitor_name FROM visitors WHERE id = %s", (visitor_id,))
        v_info = cursor.fetchone()
        if v_info:
            send_host_approval_email(v_info['person_to_meet'], v_info['visitor_name'], visitor_id)
            flash("Logistics details saved and host has been alerted for approval.", "success")
            
        cursor.close()
        return redirect(url_for('main.projects_logistics'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # Get customers who requested pickup, drop or driver
    query = """
    SELECT * FROM visitors 
    WHERE (pickup_required = 1 OR drop_required = 1 OR engage_driver = 1)
    ORDER BY check_in DESC Limit 200
    """
    cursor.execute(query)
    visitors = cursor.fetchall()
    cursor.close()
    
    return render_template('projects_logistics.html', visitors=visitors, role=role)

@bp.route('/approve-logistics/<int:visitor_id>', methods=['GET', 'POST'])
def approve_visitor_logistics(visitor_id):
    if request.method == 'POST':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE visitors SET host_approval_status = 'APPROVED' WHERE id = %s", (visitor_id,))
        conn.commit()
        cursor.close()
        flash("You have successfully approved the logistics for this visitor.", "success")
        return redirect(url_for('main.index'))
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM visitors WHERE id = %s", (visitor_id,))
    visitor = cursor.fetchone()
    cursor.close()
    
    if not visitor:
        flash("Visitor record not found.", "warning")
        return redirect(url_for('main.index'))
        
    return render_template('approve_logistics.html', visitor=visitor)

@bp.route('/inbox')
@login_required
def inbox():
    """Intelligence Inbox: A Gmail-style view of all approvals and alerts."""
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    user_id = session.get('user_id')
    role = session.get('role', '')
    username = session.get('username', '')
    
    # Query parameters for filtering
    filter_type = request.args.get('filter', 'inbox')  # inbox, starred, archived, snoozed, sent, drafts
    category = request.args.get('category')  # social, updates, promotions
    
    # Get user details for filtering
    cursor.execute("SELECT full_name, unit, email FROM users WHERE id = %s", (user_id,))
    user_info = cursor.fetchone()
    full_name = user_info['full_name'] if user_info else ''
    unit = user_info['unit'] if user_info else ''

    # Build SQL components based on filter
    # For visitors
    visitor_where = []
    if filter_type == 'starred':
        visitor_where.append("is_starred = 1")
    elif filter_type == 'archived':
        visitor_where.append("is_archived = 1")
    elif filter_type == 'sent':
        visitor_where.append("host_approval_status IN ('APPROVED', 'REJECTED')")
    elif filter_type == 'drafts':
        visitor_where.append("is_draft = 1")
    else: # inbox
        visitor_where.append("is_archived = 0")
        visitor_where.append("is_draft = 0")
        visitor_where.append("(snoozed_until IS NULL OR snoozed_until < NOW())")
    
    if role not in ['ADMIN', 'RECEPTION']:
        visitor_where.append("(person_to_meet = %s OR person_to_meet = %s)")

    visitor_sql = f"""
        SELECT id, visitor_name as sender, company as subject, purpose as preview, 
               'VISITOR_APPROVAL' as type, host_approval_status as status, check_in as date,
               is_starred, is_archived
        FROM visitors 
        WHERE {" AND ".join(visitor_where) if visitor_where else "1=1"}
        ORDER BY check_in DESC LIMIT 100
    """
    
    if role not in ['ADMIN', 'RECEPTION']:
        cursor.execute(visitor_sql, (username, full_name))
    else:
        cursor.execute(visitor_sql)
    inbox_items = cursor.fetchall()
    
    # For fleet_bookings
    fleet_items = []
    if role in ['ADMIN', 'LOGISTICS'] or (unit and unit.lower().find('fleet') != -1):
        fleet_where = []
        if filter_type == 'starred': fleet_where.append("fb.is_starred = 1")
        elif filter_type == 'archived': fleet_where.append("fb.is_archived = 1")
        else: fleet_where.append("fb.is_archived = 0")
        
        fleet_sql = f"""
            SELECT fb.id, v.visitor_name as sender, CONCAT('Fleet: ', fb.trip_type) as subject, 
                   CONCAT('Route: ', fb.from_location, ' to ', fb.to_location) as preview,
                   'FLEET_APPROVAL' as type, fb.department_approval_status as status, fb.created_at as date,
                   fb.is_starred, fb.is_archived
            FROM fleet_bookings fb
            JOIN visitors v ON fb.visitor_id = v.id
            WHERE {" AND ".join(fleet_where) if fleet_where else "1=1"}
            ORDER BY fb.created_at DESC LIMIT 50
        """
        cursor.execute(fleet_sql)
        fleet_items = cursor.fetchall()

    # For Security Alerts
    alert_items = []
    if role in ['ADMIN', 'SECURITY']:
        alert_where = []
        if filter_type == 'starred': alert_where.append("sa.is_starred = 1")
        elif filter_type == 'archived': alert_where.append("sa.is_archived = 1")
        else: alert_where.append("sa.is_archived = 0")
        
        alert_sql = f"""
            SELECT id, 'SECURITY' as sender, title as subject, message as preview,
                   'SECURITY_ALERT' as type, 'ALERT' as status, created_at as date,
                   is_starred, is_archived
            FROM security_alerts sa
            WHERE {" AND ".join(alert_where) if alert_where else "1=1"}
            ORDER BY created_at DESC LIMIT 50
        """
        cursor.execute(alert_sql)
        alert_items = cursor.fetchall()
    
    # 4. Filter by Category if requested
    if category == 'social':
        inbox_items = [i for i in inbox_items if i['type'] == 'VISITOR_APPROVAL']
        fleet_items = []
        alert_items = []
    elif category == 'updates':
        inbox_items = []
        fleet_items = [i for i in fleet_items if i['type'] == 'FLEET_APPROVAL']
        alert_items = []
    elif category == 'promotions':
        inbox_items = []
        fleet_items = []
        alert_items = [i for i in alert_items if i['type'] == 'SECURITY_ALERT']

    # Combine and sort by date
    all_items = inbox_items + fleet_items + alert_items
    all_items.sort(key=lambda x: x['date'] if x['date'] else datetime.min, reverse=True)
    
    cursor.close()
    return render_template('inbox.html', items=all_items, role=role, user_info=user_info, now=datetime.now(), current_filter=filter_type)

@bp.route('/api/inbox/star', methods=['POST'])
@login_required
def inbox_toggle_star():
    data = request.json
    item_id = data.get('id')
    item_type = data.get('type')
    is_starred = data.get('is_starred')
    
    table = 'visitors'
    if item_type == 'FLEET_APPROVAL': table = 'fleet_bookings'
    elif item_type == 'SECURITY_ALERT': table = 'security_alerts'
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE {table} SET is_starred = %s WHERE id = %s", (is_starred, item_id))
    conn.commit()
    cursor.close()
    return jsonify({"success": True})

@bp.route('/api/inbox/archive', methods=['POST'])
@login_required
def inbox_archive():
    data = request.json
    ids_by_type = data.get('items', {}) # { 'VISITOR_APPROVAL': [1,2], ... }
    
    conn = get_db()
    cursor = conn.cursor()
    for item_type, ids in ids_by_type.items():
        if not ids: continue
        table = 'visitors'
        if item_type == 'FLEET_APPROVAL': table = 'fleet_bookings'
        elif item_type == 'SECURITY_ALERT': table = 'security_alerts'
        
        id_list = ",".join([str(i) for i in ids])
        cursor.execute(f"UPDATE {table} SET is_archived = 1 WHERE id IN ({id_list})")
    
    conn.commit()
    cursor.close()
    return jsonify({"success": True})

@bp.route('/api/inbox/delete', methods=['POST'])
@login_required
def inbox_delete():
    """
    Archive/Remove inbox items - DO NOT DELETE ACTUAL VISITOR DATA
    This should only archive approval requests, not delete visitor records
    """
    data = request.json
    ids_by_type = data.get('items', {})
    
    conn = get_db()
    cursor = conn.cursor()
    
    for item_type, ids in ids_by_type.items():
        if not ids: continue
        
        if item_type == 'VISITOR_APPROVAL':
            # For visitor approvals, we should NOT delete the visitor record
            # Instead, we should mark as processed/archived or remove from inbox view
            # This is a critical fix - DO NOT DELETE VISITOR DATA
            
            # Option 1: Mark as processed (recommended)
            id_list = ",".join([str(i) for i in ids])
            cursor.execute(f"UPDATE visitors SET inbox_processed = 1 WHERE id IN ({id_list})")
            
            # Option 2: Create an archive table (better approach)
            # cursor.execute(f"INSERT INTO inbox_archive (visitor_id, item_type, archived_at, archived_by) VALUES ({id_list}, 'VISITOR_APPROVAL', NOW(), %s)", (session.get('user_id')))
            
        elif item_type == 'FLEET_APPROVAL':
            # For fleet approvals, mark as processed instead of deleting
            id_list = ",".join([str(i) for i in ids])
            cursor.execute(f"UPDATE fleet_bookings SET inbox_processed = 1 WHERE id IN ({id_list})")
            
        elif item_type == 'SECURITY_ALERT':
            # For security alerts, mark as resolved instead of deleting
            id_list = ",".join([str(i) for i in ids])
            cursor.execute(f"UPDATE security_alerts SET status = 'RESOLVED', inbox_processed = 1 WHERE id IN ({id_list})")
    
    conn.commit()
    cursor.close()
    return jsonify({"success": True, "message": "Items archived from inbox successfully"})

@bp.route('/host-approvals', methods=['GET'])
@login_required
def host_approvals():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    role = session.get('role', '')
    # Fetch all pre-registered + approved visitors (full pipeline visible to admin/security)
    cols = "id, visitor_name, company, phone, email, photo, purpose, person_to_meet, check_in, status, host_approval_status, approval_notes, approved_at, approved_by, rejected_reason, security_checkin_at, kiosk_self_registered, expected_duration"
    if role in ['ADMIN', 'SECURITY', 'RECEPTION']:
        cursor.execute(f"SELECT {cols} FROM visitors WHERE status IN ('PRE_REGISTERED','IN') OR host_approval_status IN ('APPROVED','REJECTED') ORDER BY check_in DESC LIMIT 200")
    elif role == 'HOST':
        username = session.get('username', '')
        cursor.execute("SELECT full_name FROM users WHERE id = %s", (session.get('user_id'),))
        u = cursor.fetchone()
        full_name = u['full_name'] if u else ''
        cursor.execute(f"SELECT {cols} FROM visitors WHERE (status = 'PRE_REGISTERED' OR host_approval_status IN ('APPROVED','REJECTED')) AND (person_to_meet = %s OR person_to_meet = %s) ORDER BY check_in DESC", (username, full_name))
    else:
        cursor.close()
        flash("You do not have permission to view host approvals.", "danger")
        return redirect(url_for('main.index'))
        
    visitors = cursor.fetchall()
    cursor.close()
    return render_template('host_approvals.html', visitors=visitors, role=role)


@bp.route('/security', methods=['GET'])
@login_required
def security_dashboard():
    """Dedicated dashboard for Security role: shows only Add Visitor + Badge-Ready queue."""
    role = session.get('role', '')
    if role not in ['SECURITY', 'ADMIN']:
        flash("Access restricted to Security personnel.", "danger")
        return redirect(url_for('main.index'))

    username = session.get('username', '')
    unit = session.get('unit', '')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Visitors that are APPROVED and waiting for badge (not yet checked in)
    cursor.execute("""
        SELECT id, visitor_name, company, phone, purpose, person_to_meet,
               host_approval_status, status, approved_at, approved_by,
               approval_notes, kiosk_self_registered, check_in
        FROM visitors
        WHERE host_approval_status = 'APPROVED' AND status = 'PRE_REGISTERED'
        ORDER BY approved_at DESC
        LIMIT 50
    """)
    ready_for_badge = cursor.fetchall()

    # Recent visitors entered today (by check-in date or without date, fallback to last 20)
    try:
        cursor.execute("""
            SELECT id, visitor_name, company, phone, purpose, person_to_meet, status,
                   host_approval_status, check_in, kiosk_self_registered
            FROM visitors
            WHERE DATE(check_in) = CURDATE()
            ORDER BY check_in DESC
            LIMIT 20
        """)
    except Exception:
        cursor.execute("""
            SELECT id, visitor_name, company, phone, purpose, person_to_meet, status,
                   host_approval_status, check_in, kiosk_self_registered
            FROM visitors
            ORDER BY id DESC
            LIMIT 20
        """)
    today_visitors = cursor.fetchall()

    # Count stats
    cursor.execute("SELECT COUNT(*) as cnt FROM visitors WHERE host_approval_status='PENDING' AND status='PRE_REGISTERED'")
    pending_count = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM visitors WHERE host_approval_status='APPROVED' AND status='PRE_REGISTERED'")
    badge_ready_count = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM visitors WHERE status='IN' AND DATE(check_in)=CURDATE()")
    checked_in_today = cursor.fetchone()['cnt']

    cursor.close()

    return render_template('security_dashboard.html',
        ready_for_badge=ready_for_badge,
        today_visitors=today_visitors,
        pending_count=pending_count,
        badge_ready_count=badge_ready_count,
        checked_in_today=checked_in_today,
        username=username, unit=unit, role=role
    )

def add_security_alert(type, title, message, visitor_id=None, action_url=None):
    """
    Utility to store a security alert in the database.
    Types: CRITICAL, WARNING, INFO, SUCCESS
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO security_alerts (type, title, message, visitor_id, action_url) VALUES (%s, %s, %s, %s, %s)",
            (type, title, message, visitor_id, action_url)
        )
        conn.commit()
        cursor.close()
        return True
    except Exception as e:
        print(f"[ALERT_ERROR] {e}")
        return False

@bp.route('/api/security/alerts', methods=['GET'])
@login_required
def api_security_alerts():
    """Fetch recent unread security alerts."""
    role = session.get('role', '')
    if role not in ['SECURITY', 'ADMIN']:
        return jsonify([])
    
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, type, title, message, visitor_id, action_url, created_at FROM security_alerts WHERE is_read = 0 ORDER BY created_at DESC LIMIT 50")
        alerts = cursor.fetchall()
        cursor.close()
        
        for a in alerts:
            # Handle timezone/formatting
            if a['created_at']:
                a['created_at_str'] = a['created_at'].strftime('%H:%M:%S')
            else:
                a['created_at_str'] = 'Now'
            del a['created_at'] # JSON can't handle datetimes directly
            
        return jsonify(alerts)
    except Exception as e:
        print(f"[API_ALERT_ERROR] {e}")
        return jsonify([])

@bp.route('/api/security/alerts/read/<int:alert_id>', methods=['POST'])
@login_required
def api_security_alert_read(alert_id):
    """Mark an alert as read."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE security_alerts SET is_read = 1 WHERE id = %s", (alert_id,))
        conn.commit()
        cursor.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/host-approve-visitor/<int:visitor_id>', methods=['POST'])
@login_required
def host_approve_visitor(visitor_id):
    role = session.get('role', '')
    if role not in ['ADMIN', 'HOST', 'SECURITY', 'RECEPTION']:
        flash("Permission denied.", "danger")
        return redirect(url_for('main.index'))
        
    action = request.form.get('action')
    approval_notes = request.form.get('approval_notes', '').strip()
    rejected_reason = request.form.get('rejected_reason', '').strip()
    approver = session.get('username', 'Admin')
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    if role == 'HOST':
        cursor.execute("SELECT full_name FROM users WHERE id = %s", (session.get('user_id'),))
        u = cursor.fetchone()
        full_name = u['full_name'] if u else ''
        username = session.get('username', '')
        
        cursor.execute("SELECT id, visitor_name FROM visitors WHERE id = %s AND (person_to_meet = %s OR person_to_meet = %s)", (visitor_id, username, full_name))
        if not cursor.fetchone():
            flash("You can only approve your own visitors.", "danger")
            cursor.close()
            return redirect(url_for('main.host_approvals'))
            
    if action == 'approve':
        cursor.execute(
            "UPDATE visitors SET host_approval_status = 'APPROVED', approved_at = NOW(), approved_by = %s, approval_notes = %s WHERE id = %s",
            (approver, approval_notes or None, visitor_id)
        )
        conn.commit()
        
        # ADD SECURITY ALERT
        cursor.execute("SELECT visitor_name FROM visitors WHERE id = %s", (visitor_id,))
        v_name = cursor.fetchone()['visitor_name']
        add_security_alert(
            'SUCCESS', 
            'Visitor Approved', 
            f'{v_name} has been approved by {approver}. Please print badge.', 
            visitor_id, 
            url_for('main.security_dashboard')
        )

        flash("✅ Visitor approved! Host and security have been notified.", "success")
        # Try to send email notification
        try:
            cursor.execute("SELECT visitor_name, person_to_meet FROM visitors WHERE id = %s", (visitor_id,))
            vi = cursor.fetchone()
            if vi:
                send_host_approval_email(vi['person_to_meet'], vi['visitor_name'], visitor_id)
        except Exception:
            pass
        
    elif action == 'reject':
        cursor.execute(
            "UPDATE visitors SET host_approval_status = 'REJECTED', status = 'REJECTED', rejected_reason = %s, approved_by = %s WHERE id = %s",
            (rejected_reason or 'No reason provided', approver, visitor_id)
        )
        conn.commit()
        flash("❌ Visitor has been rejected.", "danger")
        
    elif action == 'checkin':
        cursor.execute("SELECT host_approval_status FROM visitors WHERE id = %s", (visitor_id,))
        v = cursor.fetchone()
        if v and v['host_approval_status'] == 'APPROVED':
            cursor.execute(
                "UPDATE visitors SET status = 'IN', check_in = NOW(), security_checkin_at = NOW() WHERE id = %s",
                (visitor_id,)
            )
            conn.commit()
            flash("🎫 Badge assigned & visitor checked in successfully!", "success")
            cursor.close()
            # Redirect to badge page
            return redirect(url_for('main.badge', id=visitor_id))
        else:
            flash("Visitor must be approved by the host before check-in.", "warning")
            
    cursor.close()
    return redirect(url_for('main.host_approvals'))

@bp.route('/update-welcome-note/<int:visitor_id>', methods=['POST'])
@login_required
def update_welcome_note(visitor_id):
    role = session.get('role', '')
    if role not in ['ADMIN', 'RECEPTION']:
        flash("Permission denied.", "danger")
        return redirect(url_for('main.view_visitor', id=visitor_id))
        
    welcome_note = request.form.get('welcome_note')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE visitors SET welcome_note = %s WHERE id = %s", (welcome_note, visitor_id))
    conn.commit()
    cursor.close()
    
    flash("Customer Welcome Note updated successfully.", "success")
    return redirect(url_for('main.view_visitor', id=visitor_id))

# --- Visitor Self-Service Kiosk Routes ---

@bp.route('/kiosk', methods=['GET'])
def kiosk():
    """Public facing self-service visitor registration kiosk."""
    return render_template('kiosk.html')

@bp.route('/kiosk/register', methods=['POST'])
def kiosk_register():
    """Handle kiosk self-registration submission."""
    from datetime import datetime
    visitor_name = request.form.get('visitor_name', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip()
    company = request.form.get('company', '').strip()
    purpose = request.form.get('purpose', 'General Visit').strip()
    person_to_meet = request.form.get('person_to_meet', '').strip()
    expected_duration = request.form.get('expected_duration', '1 hr').strip()
    draft_notes = request.form.get('draft_notes', '').strip()

    if not visitor_name or not phone or not company:
        flash("Name, Phone, and Company are required.", "danger")
        return redirect(url_for('main.kiosk'))

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO visitors
               (visitor_name, phone, email, company, purpose, person_to_meet,
                expected_duration, status, host_approval_status, kiosk_self_registered,
                draft_notes, check_in)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'PRE_REGISTERED','PENDING',1,%s,NOW())""",
            (visitor_name, phone, email or None, company, purpose, person_to_meet,
             expected_duration, draft_notes or None)
        )
        visitor_id = cursor.lastrowid
        conn.commit()
        
        # ADD SECURITY ALERT
        add_security_alert(
            'INFO', 
            'New Kiosk Registration', 
            f'Visitor {visitor_name} (from {company}) just self-registered at the kiosk.', 
            visitor_id, 
            url_for('main.security_dashboard')
        )

        cursor.close()

        # Try host notification
        try:
            send_host_approval_email(person_to_meet, visitor_name, visitor_id)
        except Exception:
            pass

        flash(f"Thank you {visitor_name}! Your visit request has been submitted. Please wait at reception while the host is notified.", "success")
        return redirect(url_for('main.kiosk_success', visitor_id=visitor_id))

    except Exception as e:
        flash(f"Registration error: {e}", "danger")
        return redirect(url_for('main.kiosk'))


@bp.route('/kiosk/success/<int:visitor_id>')
def kiosk_success(visitor_id):
    """Kiosk success page shown to visitor after self-registration."""
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, visitor_name, company, purpose, person_to_meet, host_approval_status FROM visitors WHERE id=%s", (visitor_id,))
        visitor = cursor.fetchone()
        cursor.close()
    except Exception:
        visitor = None
    return render_template('kiosk_success.html', visitor=visitor)

# --- COMMUNICATION HUB / EMAIL ALERTS ROUTES ---

@bp.route('/email-alerts')
@login_required
def email_alerts():
    """Communication Hub: Manage who gets notified for which department."""
    if session.get('role') != 'ADMIN':
        flash("Unauthorized: Admin access required.", "danger")
        return redirect(url_for('main.index'))
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM email_alert_settings ORDER BY department ASC")
    settings = cursor.fetchall()
    
    # Get unique departments from visitors to help with suggestions
    cursor.execute("SELECT DISTINCT company FROM visitors WHERE company IS NOT NULL")
    companies = [r['company'] for r in cursor.fetchall()]
    
    cursor.close()
    return render_template('email_alerts.html', settings=settings, companies=companies)

@bp.route('/api/email-alerts/save', methods=['POST'])
@login_required
def save_email_alert():
    if session.get('role') != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.json
    id = data.get('id')
    dept = data.get('department')
    person = data.get('key_person')
    email = data.get('email')
    priority = data.get('priority', 'MEDIUM')
    frequency = data.get('frequency', 'IMMEDIATE')
    
    if not dept or not person or not email:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if id:
            # Update existing
            cursor.execute("""
                UPDATE email_alert_settings 
                SET department=%s, key_person=%s, email=%s, priority=%s, frequency=%s
                WHERE id = %s
            """, (dept, person, email, priority, frequency, id))
            msg = 'Protocol updated successfully'
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO email_alert_settings (department, key_person, email, priority, frequency)
                VALUES (%s, %s, %s, %s, %s)
            """, (dept, person, email, priority, frequency))
            msg = 'Protocol established successfully'
            
        conn.commit()
        cursor.close()
        return jsonify({'success': True, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/email-alerts/test/<int:id>', methods=['POST'])
@login_required
def test_email_alert(id):
    """Simulate sending a test alert to verify configuration."""
    if session.get('role') != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
        
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM email_alert_settings WHERE id = %s", (id,))
        setting = cursor.fetchone()
        
        if not setting:
            return jsonify({'success': False, 'message': 'Setting not found'}), 404
            
        # Update last_triggered and count for the test
        cursor.execute("UPDATE email_alert_settings SET last_triggered_at=NOW(), trigger_count = trigger_count + 1 WHERE id = %s", (id,))
        
        # Log to communication history
        cursor.execute("""
            INSERT INTO communication_history (setting_id, status, details)
            VALUES (%s, 'SUCCESS', %s)
        """, (id, f"Diagnostic alert dispatched to {setting['email']} via system protocol."))
        
        conn.commit()
        cursor.close()
        return jsonify({'success': True, 'message': f"Test alert successfully routed to {setting['email']}."})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/email-alerts/bulk-toggle', methods=['POST'])
@login_required
def bulk_toggle_alerts():
    if session.get('role') != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    enabled = request.json.get('enabled', True)
    category = request.json.get('category', 'ALL')
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        if category == 'ALL':
            cursor.execute("UPDATE email_alert_settings SET alerts_enabled = %s", (1 if enabled else 0,))
        elif category == 'CRITICAL':
            cursor.execute("UPDATE email_alert_settings SET alerts_enabled = %s WHERE priority = 'CRITICAL'", (1 if enabled else 0,))
        
        conn.commit()
        cursor.close()
        return jsonify({'success': True, 'message': f"All {category} protocols {'restored' if enabled else 'suspended'}."})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/email-alerts/analytics')
@login_required
def get_alert_analytics():
    """Fetch time-series data for alert triggers over the last 7 days."""
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT DATE(triggered_at) as date, COUNT(*) as count 
            FROM communication_history 
            GROUP BY date 
            ORDER BY date ASC 
            LIMIT 7
        """)
        history = cursor.fetchall()
        
        # Priority distribution
        cursor.execute("""
            SELECT priority, COUNT(*) as count 
            FROM email_alert_settings 
            GROUP BY priority
        """)
        distribution = cursor.fetchall()
        
        cursor.close()
        return jsonify({
            'success': True, 
            'timeline': history,
            'distribution': distribution
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/email-alerts/history/<int:id>')
@login_required
def get_alert_history(id):
    """Fetch recent history for a specific protocol."""
    try:
        conn = get_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM communication_history 
            WHERE setting_id = %s 
            ORDER BY triggered_at DESC 
            LIMIT 10
        """, (id,))
        logs = cursor.fetchall()
        cursor.close()
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
        
        return jsonify({
            'success': True, 
            'message': f"Test email dispatched to {setting['email']} ({setting['key_person']}). Diagnostic ping successful!"
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/email-alerts/toggle/<int:id>', methods=['POST'])
@login_required
def toggle_email_alert(id):
    if session.get('role') != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE email_alert_settings SET alerts_enabled = NOT alerts_enabled WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@bp.route('/api/email-alerts/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_email_alert(id):
    if session.get('role') != 'ADMIN':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM email_alert_settings WHERE id = %s", (id,))
        conn.commit()
        cursor.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
