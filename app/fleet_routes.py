# Fleet and Logistics Endpoints
from flask import request, jsonify, render_template, redirect, url_for, flash, session
from app.db import get_db
from app.routes import bp, login_required

@bp.route('/fleet', methods=['GET'])
@login_required
def fleet_management():
    # Only Admin, Projects, Logistics can see this
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM drivers")
    drivers = cursor.fetchall()
    
    cursor.execute("SELECT * FROM vehicles")
    vehicles = cursor.fetchall()
    cursor.close()
    
    return render_template('fleet_management.html', drivers=drivers, vehicles=vehicles)

@bp.route('/api/fleet/add_driver', methods=['POST'])
@login_required
def add_driver():
    name = request.form.get('name')
    phone = request.form.get('phone')
    license_number = request.form.get('license_number')
    department = request.form.get('department')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO drivers (name, phone, license_number, department) VALUES (%s, %s, %s, %s)",
                   (name, phone, license_number, department))
    conn.commit()
    cursor.close()
    return redirect(url_for('main.fleet_management'))

@bp.route('/api/fleet/add_vehicle', methods=['POST'])
@login_required
def add_vehicle():
    brand = request.form.get('brand')
    model = request.form.get('model')
    plate_number = request.form.get('plate_number')
    capacity = request.form.get('capacity', 4)
    department = request.form.get('department')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO vehicles (brand, model, plate_number, capacity, department) VALUES (%s, %s, %s, %s, %s)",
                   (brand, model, plate_number, capacity, department))
    conn.commit()
    cursor.close()
    return redirect(url_for('main.fleet_management'))

@bp.route('/api/fleet/get_availability', methods=['GET'])
@login_required
def get_driver_availability():
    date = request.args.get('date')
    trip_type = request.args.get('trip_type', 'pickup') # pickup or drop
    
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get all matching drivers
    cursor.execute("SELECT id, name, phone, department, status FROM drivers WHERE status = 'AVAILABLE'")
    drivers = cursor.fetchall()
    
    # Get all bookings on this date
    cursor.execute("""
        SELECT driver_id, start_time, end_time, trip_type 
        FROM fleet_bookings 
        WHERE trip_date = %s
    """, (date,))
    bookings = cursor.fetchall()
    
    # Process into slots
    for driver in drivers:
        d_books = [b for b in bookings if b['driver_id'] == driver['id']]
        driver['bookings'] = d_books
        driver['booked_slots_count'] = len(d_books)
        
    cursor.close()
    return jsonify({"success": True, "drivers": drivers})

def send_fleet_approval_alert(booking_id, visitor_name, driver_name, trip_type, department, to_email):
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
            print(f"No SMTP settings. Fleet approval email to {to_email} simulated.")
            return False

        SMTP_SERVER = settings['server']
        SMTP_PORT = settings['port']
        SMTP_USER = settings['username']
        SMTP_PASS = settings['password']

        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = f"Action Required: Fleet Booking Approval for {visitor_name}"

        approval_link = url_for('main.department_approvals', _external=True)

        body = f"""
Fleet driver slot allocation is pending your approval.

Visitor: {visitor_name}
Driver Assigned: {driver_name}
Type of Trip: {trip_type}
Logistics Dept: {department}

Please log into the Visitor Portal and navigate to the "Department Approvals" tab, or click the link below to review:
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
        print(f"Failed to send fleet approval alert: {e}")
        return False

@bp.route('/api/fleet/book_driver', methods=['POST'])
@login_required
def book_driver():
    data = request.json
    visitor_id = data.get('visitor_id')
    driver_id = data.get('driver_id')
    vehicle_id = data.get('vehicle_id')
    trip_type = data.get('trip_type')
    trip_date = data.get('trip_date')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    from_location = data.get('from_location')
    to_location = data.get('to_location')
    department = data.get('department') # Target department for approval

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO fleet_bookings 
        (visitor_id, driver_id, vehicle_id, trip_type, trip_date, start_time, end_time, from_location, to_location, department_approval_status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDING')
    """, (visitor_id, driver_id, vehicle_id, trip_type, trip_date, start_time, end_time, from_location, to_location))
    
    booking_id = cursor.lastrowid
    
    # Automatically allocate details string in the visitors table
    cursor.execute("SELECT name FROM drivers WHERE id = %s", (driver_id,))
    driver_name = cursor.fetchone()[0]
    detail_string = f"Driver: {driver_name} (Slot: {start_time} - {end_time})"
    
    if trip_type == 'PICKUP':
        cursor.execute("UPDATE visitors SET pickup_details = %s WHERE id = %s", (detail_string, visitor_id))
    elif trip_type == 'DROP':
        cursor.execute("UPDATE visitors SET drop_details = %s WHERE id = %s", (detail_string, visitor_id))
        
    # Get visitor info to send alert email
    cursor.execute("SELECT visitor_name, assigned_department_email, person_to_meet FROM visitors WHERE id = %s", (visitor_id,))
    v_info = cursor.fetchone()
    
    conn.commit()
    cursor.close()
    
    # Try resolving an email destination
    to_email = None
    if v_info:
        visitor_name, dept_email, host_name = v_info
        if dept_email:
            to_email = dept_email
        elif host_name:
            # Fall back to resolving the host's email
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM users WHERE full_name = %s LIMIT 1", (host_name,))
            host_user = cursor.fetchone()
            if host_user and host_user[0]:
                to_email = host_user[0]
            cursor.close()
            
    if to_email:
        send_fleet_approval_alert(booking_id, visitor_name, driver_name, trip_type, department, to_email)
        message = f"Driver booked successfully. Alert sent to {to_email}."
    else:
        message = "Driver booked successfully. (Could not resolve a Host or Department email to alert)."
        
    return jsonify({"success": True, "message": message})

@bp.route('/department-approvals')
@login_required
def department_approvals():
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    # Fetch all fleet bookings that are pending
    cursor.execute("""
        SELECT fb.*, v.visitor_name, v.company, d.name as driver_name, veh.plate_number
        FROM fleet_bookings fb
        JOIN visitors v ON fb.visitor_id = v.id
        LEFT JOIN drivers d ON fb.driver_id = d.id
        LEFT JOIN vehicles veh ON fb.vehicle_id = veh.id
        ORDER BY fb.created_at DESC
    """)
    bookings = cursor.fetchall()
    cursor.close()
    
    return render_template('department_approvals.html', bookings=bookings)

@bp.route('/api/fleet/approve_booking/<int:booking_id>', methods=['POST'])
@login_required
def approve_booking(booking_id):
    action = request.json.get('action') # 'APPROVE' or 'REJECT'
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE fleet_bookings SET department_approval_status = %s WHERE id = %s", (action, booking_id))
    conn.commit()
    cursor.close()
    return jsonify({"success": True, "message": f"Booking was {action}D successfully."})
