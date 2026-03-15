# 🛡️ Visitor Portal System - Enterprise Edition

Welcome to the **Visitor Portal**, a comprehensive security and visitor management solution designed for modern facilities. This system streamlines the check-in process, enhances security with digital badges, and provides robust analytics.

---

## 📚 Documentation Hub

### 1. [📖 User Manual & Operational Guide](./USER_MANUAL.html)
**Target Audience:** Security Guards, Receptionists, Administrators.
*   **Click the link above** to open the interactive User Guide in your browser.
*   Includes step-by-step instructions for:
    *   Logging In
    *   Registering Visitors (Scanning, Webcams)
    *   Searching & Filtering Logs
    *   Printing & Validating Badges
    *   Exporting Reports

### 2. [⚙️ Installation & Setup Guide](#-installation--setup)
**Target Audience:** IT Administrators, Developers.
*   See below for instructions on how to set up the server, database, and run the application.

### 3. [🧑‍💻 Developer Notes](#-developer-notes)
**Target Audience:** Developers.
*   Information about the tech stack, folder structure, and customization.

---

## 🛠️ Installation & Setup

Follow these steps to deploy the Visitor Portal on a Windows machine.

### Prerequisites
*   **Python 3.8+** installed.
*   **MySQL Server** installed and running.

### Step 1: Clone or Download
Ensure all project files are in a local directory (e.g., `C:\VisitorPortal`).

### Step 2: Install Dependencies
Open a terminal in the project folder and run:
```bash
pip install -r requirements.txt
```

### Step 3: Database Configuration
1.  Open your MySQL Client (Workbench or Command Line).
2.  Create a new database:
    ```sql
    CREATE DATABASE visitor_db;
    ```
3.  **Configure Credentials**:
    *   Open `config.py` in a text editor.
    *   Update `MYSQL_USER`, `MYSQL_PASSWORD` with your local MySQL credentials.

### Step 4: Initialize Data
Run the seeding script to create the table and populate it with test data:
```bash
python seed_visitors.py
```
*   *Note: This creates an 'admin' user with password 'password123'.*

### Step 5: Run the Application
Start the Flask server:
```bash
python run.py
```
*   The application will start at: `http://localhost:5000`

---

## 🚀 Running the Application

1.  **Start the Server**: Double-click `run.py` or run `python run.py` in terminal.
2.  **Access Dashboard**: Open your browser and go to `http://localhost:5000`.
3.  **Login**:
    *   **Username:** `admin`
    *   **Password:** `password123`

---

## 📂 Developer Notes

### Folder Structure
*   `app/` - Core application logic.
    *   `routes.py` - Python backend logic, routing, and database interactions.
    *   `templates/` - HTML files (Dashboard, Logs, Badge, etc.).
    *   `static/` - CSS, Images, and JavaScript assets.
*   `config.py` - Database connection settings.
*   `run.py` - Entry point to start the web server.

### Key Features Under the Hood
*   **Robust Error Handling**: The frontend is designed to handle malformed data gracefully without crashing.
*   **Secure Filtering**: Backend SQL queries use parameterized inputs to prevent injection attacks.
*   **Dynamic UI**: Uses pure JavaScript and CSS (no heavy frontend frameworks) for maximum performance and easy maintenance.

---

## 📞 Support

For technical support or feature requests, please contact the IT Department.

**© 2026 Visitor Portal Systems**
