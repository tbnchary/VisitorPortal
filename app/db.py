import mysql.connector
from mysql.connector import pooling
from flask import current_app, g
import os

db_pool = None

def get_db():
    global db_pool
    if 'db' not in g:
        connect_args = {
            'host': current_app.config['MYSQL_HOST'],
            'user': current_app.config['MYSQL_USER'],
            'password': current_app.config['MYSQL_PASSWORD'],
            'database': current_app.config['MYSQL_DB'],
            'connection_timeout': 3  # Ensure Vercel doesn't kill the function before timeout
        }
        
        # Add port if it exists in config
        if current_app.config.get('MYSQL_PORT'):
            connect_args['port'] = int(current_app.config['MYSQL_PORT'])
        
        # TiDB Cloud requires SSL to be enabled
        if 'gateway' in connect_args['host'] or 'tidb' in connect_args['host']:
            connect_args['ssl_disabled'] = False
            connect_args['ssl_verify_cert'] = False
            connect_args['ssl_verify_identity'] = False

        # If on Vercel and host is localhost, fail fast
        if os.environ.get('VERCEL') == '1' and connect_args['host'] in ['localhost', '127.0.0.1']:
            raise Exception("Vercel cannot connect to a localhost database. Please configure a remote MySQL database in Vercel Environment Variables.")

        # Initialize connection pool if not already initialized to speed up page loads
        if db_pool is None:
            connect_args['pool_name'] = "vercel_pool"
            connect_args['pool_size'] = 5
            connect_args['pool_reset_session'] = True
            db_pool = mysql.connector.pooling.MySQLConnectionPool(**connect_args)

        g.db = db_pool.get_connection()
    return g.db

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close() # For pooled connections, this returns it to the pool instead of closing!

def init_app(app):
    app.teardown_appcontext(close_db)
    
    # Skip automatic table initialization on Vercel to dramatically speed up cold starts!
    if os.environ.get('VERCEL') == '1':
        print("Skipping automatic database initialization for Vercel deployment.")
        return
        
    with app.app_context():
        try:
            ensure_users_table()
            ensure_fleet_tables()
            ensure_logistics_tables()
            ensure_sidebar_menu()
            ensure_user_columns()
            ensure_visitor_columns()
            ensure_menu_items_for_projects()
            ensure_department_approvals_menu()
            ensure_host_approvals_menu()
            ensure_security_alerts_table()
            ensure_email_alert_settings()
            ensure_inbox_menu()
            ensure_inbox_columns()
        except Exception as e:
            print(f"Warning: Could not initialize database tables at startup: {e}")

def ensure_users_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            full_name VARCHAR(100) NOT NULL,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(20),
            password VARCHAR(255) NOT NULL,
            role ENUM('ADMIN', 'RECEPTION', 'SECURITY', 'HOST') DEFAULT 'RECEPTION',
            status ENUM('PENDING', 'APPROVED', 'REJECTED') DEFAULT 'PENDING',
            unit VARCHAR(255)
        )
    ''')
    conn.commit()
    cursor.close()

def ensure_inbox_columns():
    conn = get_db()
    cursor = conn.cursor()
    tables = ['visitors', 'fleet_bookings', 'security_alerts']
    new_cols = {
        'is_starred': 'TINYINT(1) DEFAULT 0',
        'is_archived': 'TINYINT(1) DEFAULT 0',
        'snoozed_until': 'DATETIME'
    }
    for table in tables:
        try:
            cursor.execute(f"DESCRIBE {table}")
            columns = [row[0] for row in cursor.fetchall()]
            for col, data_type in new_cols.items():
                if col not in columns:
                    print(f"DEBUG: Adding {col} to {table}")
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {data_type}")
        except Exception as e:
            print(f"DEBUG: Error ensuring columns for {table}: {e}")
    conn.commit()
    cursor.close()

def ensure_security_alerts_table():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS security_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            type VARCHAR(50) NOT NULL,
            title VARCHAR(100) NOT NULL,
            message TEXT,
            visitor_id INT,
            action_url VARCHAR(255),
            is_read TINYINT(1) DEFAULT 0,
            is_starred TINYINT(1) DEFAULT 0,
            is_archived TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (visitor_id) REFERENCES visitors(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    cursor.close()

def ensure_email_alert_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_alert_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            department VARCHAR(100) NOT NULL,
            key_person VARCHAR(100) NOT NULL,
            email VARCHAR(150) NOT NULL,
            priority ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') DEFAULT 'MEDIUM',
            frequency ENUM('IMMEDIATE', 'DAILY_DIGEST', 'HOURLY_SUMMARY') DEFAULT 'IMMEDIATE',
            alerts_enabled TINYINT(1) DEFAULT 1,
            last_triggered_at TIMESTAMP NULL,
            trigger_count INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Check for missing columns (migration)
    cursor.execute("DESCRIBE email_alert_settings")
    columns = [row[0] for row in cursor.fetchall()]
    if 'priority' not in columns:
        cursor.execute("ALTER TABLE email_alert_settings ADD COLUMN priority ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') DEFAULT 'MEDIUM' AFTER email")
    if 'frequency' not in columns:
        cursor.execute("ALTER TABLE email_alert_settings ADD COLUMN frequency ENUM('IMMEDIATE', 'DAILY_DIGEST', 'HOURLY_SUMMARY') DEFAULT 'IMMEDIATE' AFTER priority")
    if 'last_triggered_at' not in columns:
        cursor.execute("ALTER TABLE email_alert_settings ADD COLUMN last_triggered_at TIMESTAMP NULL AFTER alerts_enabled")
    if 'trigger_count' not in columns:
        cursor.execute("ALTER TABLE email_alert_settings ADD COLUMN trigger_count INT DEFAULT 0 AFTER last_triggered_at")

    # History tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS communication_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_id INT,
            status VARCHAR(50) DEFAULT 'SUCCESS',
            details TEXT,
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (setting_id) REFERENCES email_alert_settings(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    cursor.close()

def ensure_host_approvals_menu():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as count FROM sidebar_menu WHERE name='host_approvals'")
    if cursor.fetchone()['count'] == 0:
        cursor.execute('''
            INSERT INTO sidebar_menu (name, label, icon, url, enabled, ordering)
            VALUES ('host_approvals', 'Host Approvals', 'bi bi-person-check', '/host-approvals', 1, 6)
        ''')
        conn.commit()
    cursor.close()

def ensure_department_approvals_menu():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as count FROM sidebar_menu WHERE name='department_approvals'")
    if cursor.fetchone()['count'] == 0:
        cursor.execute('''
            INSERT INTO sidebar_menu (name, label, icon, url, enabled, ordering)
            VALUES ('department_approvals', 'Fleet Approvals', 'bi bi-shield-check', '/department-approvals', 1, 7)
        ''')
        conn.commit()
    cursor.close()

def ensure_menu_items_for_projects():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as count FROM sidebar_menu WHERE name='projects_logistics'")
    if cursor.fetchone()['count'] == 0:
        cursor.execute('''
            INSERT INTO sidebar_menu (name, label, icon, url, enabled, ordering)
            VALUES ('projects_logistics', 'Projects Logistics', 'bi bi-car-front-fill', '/projects-logistics', 1, 10)
        ''')
        conn.commit()
    cursor.close()

def ensure_inbox_menu():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as count FROM sidebar_menu WHERE name='inbox'")
    if cursor.fetchone()['count'] == 0:
        cursor.execute('''
            INSERT INTO sidebar_menu (name, label, icon, url, enabled, ordering)
            VALUES ('inbox', 'Intelligence Inbox', 'bi bi-envelope-heart', '/inbox', 1, 5)
        ''')
        conn.commit()
    cursor.close()

def ensure_visitor_columns():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DESCRIBE visitors")
    columns = [row[0] for row in cursor.fetchall()]
    new_cols = {
        'pickup_required': 'TINYINT(1) DEFAULT 0',
        'drop_required': 'TINYINT(1) DEFAULT 0',
        'food_order_details': 'TEXT',
        'engage_driver': 'TINYINT(1) DEFAULT 0',
        'assigned_department_email': 'VARCHAR(150)',
        'pickup_details': 'TEXT',
        'drop_details': 'TEXT',
        'host_approval_status': 'VARCHAR(50) DEFAULT "PENDING"',
        'transport_from_location': 'VARCHAR(255)',
        'transport_to_location': 'VARCHAR(255)',
        'transport_from_date': 'DATETIME',
        'transport_to_date': 'DATETIME',
        'pickup_from_location': 'VARCHAR(255)',
        'pickup_to_location': 'VARCHAR(255)',
        'pickup_time': 'DATETIME',
        'drop_from_location': 'VARCHAR(255)',
        'drop_to_location': 'VARCHAR(255)',
        'drop_time': 'DATETIME',
        'accompanying_members_count': 'INT DEFAULT 0',
        'accompanying_members_names': 'TEXT',
        'deletion_requested': 'TINYINT(1) DEFAULT 0',
        'is_starred': 'TINYINT(1) DEFAULT 0',
        'is_archived': 'TINYINT(1) DEFAULT 0',
        'snoozed_until': 'DATETIME'
    }
    for col, data_type in new_cols.items():
        if col not in columns:
            cursor.execute(f"ALTER TABLE visitors ADD COLUMN {col} {data_type}")
    conn.commit()
    cursor.close()

def ensure_user_columns():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DESCRIBE users")
    columns = [row[0] for row in cursor.fetchall()]
    if 'phone' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(20)")
    conn.commit()
    cursor.close()

def ensure_fleet_tables():
    conn = get_db()
    cursor = conn.cursor()
    
    # Drivers Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drivers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            phone VARCHAR(20),
            license_number VARCHAR(50),
            status VARCHAR(50) DEFAULT 'AVAILABLE',
            department VARCHAR(100)
        )
    ''')
    
    # Vehicles Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            brand VARCHAR(100) NOT NULL,
            model VARCHAR(100),
            plate_number VARCHAR(50) UNIQUE,
            capacity INT DEFAULT 4,
            status VARCHAR(50) DEFAULT 'AVAILABLE',
            department VARCHAR(100)
        )
    ''')

    # Fleet Bookings Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fleet_bookings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            visitor_id INT,
            driver_id INT,
            vehicle_id INT,
            trip_type VARCHAR(50),
            trip_date DATE,
            start_time TIME,
            end_time TIME,
            from_location VARCHAR(255),
            to_location VARCHAR(255),
            department_approval_status VARCHAR(50) DEFAULT 'PENDING',
            is_starred TINYINT(1) DEFAULT 0,
            is_archived TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (visitor_id) REFERENCES visitors(id) ON DELETE CASCADE,
            FOREIGN KEY (driver_id) REFERENCES drivers(id) ON DELETE SET NULL,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles(id) ON DELETE SET NULL
        )
    ''')
    conn.commit()
    cursor.close()

def ensure_logistics_tables():
    conn = get_db()
    cursor = conn.cursor()
    
    # SHEDS table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sheds (
            id INT AUTO_INCREMENT PRIMARY KEY,
            unique_id VARCHAR(50) UNIQUE,
            name VARCHAR(100) NOT NULL,
            customer_name VARCHAR(100),
            status VARCHAR(50) DEFAULT 'AVAILABLE',
            description TEXT
        )
    ''')
    
    # Check for missing columns in sheds (manual migration for existing tables)
    cursor.execute("DESCRIBE sheds")
    columns = [row[0] for row in cursor.fetchall()]
    if 'unique_id' not in columns:
        cursor.execute("ALTER TABLE sheds ADD COLUMN unique_id VARCHAR(50) UNIQUE AFTER id")
    if 'description' not in columns:
        cursor.execute("ALTER TABLE sheds ADD COLUMN description TEXT")
    
    # MEETING ROOMS table (Facilities)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meeting_rooms (
            id INT AUTO_INCREMENT PRIMARY KEY,
            shed_id INT,
            name VARCHAR(100) NOT NULL,
            type VARCHAR(50) NOT NULL,
            status VARCHAR(50) DEFAULT 'AVAILABLE',
            blocked_reason VARCHAR(255),
            FOREIGN KEY (shed_id) REFERENCES sheds(id) ON DELETE CASCADE
        )
    ''')
    
    # Check for missing columns in meeting_rooms
    cursor.execute("DESCRIBE meeting_rooms")
    columns = [row[0] for row in cursor.fetchall()]
    if 'type' not in columns:
        cursor.execute("ALTER TABLE meeting_rooms ADD COLUMN type VARCHAR(50) NOT NULL AFTER name")
    if 'blocked_reason' not in columns:
        cursor.execute("ALTER TABLE meeting_rooms ADD COLUMN blocked_reason VARCHAR(255)")
    if 'customer_name' not in columns:
        cursor.execute("ALTER TABLE meeting_rooms ADD COLUMN customer_name VARCHAR(100)")
    
    conn.commit()
    cursor.close()

def ensure_sidebar_menu():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sidebar_menu (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            label VARCHAR(100) NOT NULL,
            icon VARCHAR(50),
            url VARCHAR(100),
            enabled BOOLEAN DEFAULT TRUE,
            ordering INT DEFAULT 0
        )
    ''')
    conn.commit()
    # Seed with default menu items if empty
    cursor.execute('SELECT COUNT(*) as count FROM sidebar_menu')
    if cursor.fetchone()['count'] == 0:
        default_items = [
            ('dashboard', 'Dashboard', 'bi bi-grid-1x2', '/'),
            ('logs', 'Visitor Logs', 'bi bi-clock-history', '/logs'),
            ('groups', 'Visitor Groups', 'bi bi-people-fill', '/groups'),
            ('dmt', 'Data Migration Tool', 'bi bi-upload', '/dmt'),
            ('logistics', 'Logistics Hub', 'bi bi-box-seam', '/logistics'),
            ('fleet', 'Fleet & Drivers', 'bi bi-truck', '/fleet'),
            ('menu_maintenance', 'Menu Maintenance', 'bi bi-list-check', '/menu-maintenance'),
            ('add', 'Add Visitor', 'bi bi-person-plus', '/add'),
            ('export', 'Export Data', 'bi bi-download', '/export'),
            ('mobile_connect', 'Mobile Connect', 'bi bi-qr-code-scan', '/mobile-connect'),
            ('settings', 'Settings & Config', 'bi bi-gear-wide-connected', '/settings'),
            ('email_alerts', 'Communication Hub', 'bi bi-envelope-at', '/email-alerts'),
            ('user_management', 'User Management', 'bi bi-people-fill', '/user-management'),
            ('drafts', 'Draft Visitors', 'bi bi-file-earmark-text', '/drafts')
        ]
        for i, (name, label, icon, url) in enumerate(default_items):
            cursor.execute('''
                INSERT INTO sidebar_menu (name, label, icon, url, enabled, ordering)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (name, label, icon, url, True, i))
        conn.commit()
    cursor.close()
