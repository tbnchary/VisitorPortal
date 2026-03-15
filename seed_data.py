#!/usr/bin/env python3
"""
Database seeding script for Visitor Management System
Creates sample data for testing all features
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.db import get_db
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

def seed_database():
    """Seed the database with sample data for testing"""
    app = create_app()
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        
        print("🌱 Seeding database with sample data...")
        
        # Clear existing data (optional - remove if you want to keep existing data)
        print("🗑️ Clearing existing data...")
        cursor.execute("DELETE FROM users WHERE id > 1")  # Keep admin user
        
        # Create sample users
        print("👥 Creating sample users...")
        users_data = [
            {
                'username': 'john.smith',
                'full_name': 'John Smith',
                'email': 'john.smith@company.com',
                'password': 'password123',
                'role': 'HOST',
                'unit': 'Engineering',
                'phone': '+1234567890'
            },
            {
                'username': 'mary.johnson',
                'full_name': 'Mary Johnson',
                'email': 'mary.johnson@company.com',
                'password': 'password123',
                'role': 'HOST',
                'unit': 'Marketing',
                'phone': '+1234567891'
            },
            {
                'username': 'security.guard',
                'full_name': 'Security Guard',
                'email': 'security@company.com',
                'password': 'password123',
                'role': 'SECURITY',
                'unit': 'Security',
                'phone': '+1234567892'
            },
            {
                'username': 'reception.desk',
                'full_name': 'Reception Desk',
                'email': 'reception@company.com',
                'password': 'password123',
                'role': 'RECEPTION',
                'unit': 'Front Desk',
                'phone': '+1234567893'
            },
            {
                'username': 'fleet.manager',
                'full_name': 'Fleet Manager',
                'email': 'fleet@company.com',
                'password': 'password123',
                'role': 'ADMIN',
                'unit': 'Operations',
                'phone': '+1234567894'
            }
        ]
        
        for user_data in users_data:
            cursor.execute("""
                INSERT INTO users (username, full_name, email, password, role, unit, phone, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'APPROVED', NOW())
            """, (
                user_data['username'],
                user_data['full_name'],
                user_data['email'],
                user_data['password'],
                user_data['role'],
                user_data['unit'],
                user_data['phone']
            ))
        
        conn.commit()
        cursor.close()
        
        print("✅ Database seeding completed successfully!")
        print("\n📊 Sample Data Created:")
        print(f"  - {len(users_data)} users (including admin)")
        print("\n🔑 Login Credentials:")
        print("  - Username: admin / Password: admin123")
        print("  - Username: john.smith / Password: password123")
        print("  - Username: mary.johnson / Password: password123")
        print("  - Username: security.guard / Password: password123")
        print("  - Username: reception.desk / Password: password123")
        print("  - Username: fleet.manager / Password: password123")

if __name__ == "__main__":
    seed_database()
