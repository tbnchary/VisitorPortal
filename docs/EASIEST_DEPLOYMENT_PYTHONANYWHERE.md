# ☁️ Easiest Deployment: PythonAnywhere (Recommended)

This is the **absolute easiest method** to deploy your Flask + MySQL application because it handles the database and server configuration in a simple dashboard (no command line wizardry required).

**Prerequisites:**
1.  A standard PythonAnywhere account (The $5/mo "Hacker" plan is required to use your **own custom domain** and secure **HTTPS**).
2.  Your domain name provider login (e.g., GoDaddy, Namecheap).

---

## Step 1: Prepare Your Project
1.  On your computer, go to your project folder: `visitor_portal - Testing - Modules - TESTING`
2.  **Zip the entire folder** (creating `visitor_portal.zip`).

## Step 2: Upload to PythonAnywhere
1.  Log in to [PythonAnywhere.com](https://www.pythonanywhere.com/).
2.  Go to the **Files** tab.
3.  Click "Upload a file" and upload your `visitor_portal.zip`.
4.  Open a **Bash** console (from the Dashboard).
5.  Unzip the file:
    ```bash
    unzip visitor_portal.zip
    mv "visitor_portal - Testing - Modules - TESTING" mysite
    ```
    *(Note: We renamed the long folder name to `mysite` for simplicity)*

## Step 3: Setup the Database (MySQL)
1.  Go to the **Databases** tab.
2.  Under "Create a database", enter a name (e.g., `visitor_db`) and click **Create**.
3.  Click the **Password** link to set a database password.
4.  **Important:** Note down your "Database Host" address (usually `YourUsername.mysql.pythonanywhere-services.com`).

5.  **Initialize the Database:**
    *   Go back to the **Bash** console.
    *   Enter MySQL:
        ```bash
        mysql -u YourUsername -h YourUsername.mysql.pythonanywhere-services.com -p 'YourUsername$visitor_db'
        ```
        *(Enter the password you just set)*
    *   Once inside the MySQL shell, paste your database creation SQL (or run `source seed_data.sql` if you have one).

## Step 4: Configure the Web App
1.  Go to the **Web** tab.
2.  Click **Add a new web app**.
3.  Select **Manual Configuration** (since you have a custom folder structure) -> select **Python 3.10** (or your local version).
4.  **Source code:** Enter the path to your folder: `/home/YourUsername/mysite`
5.  **Virtualenv:**
    *   Open Bash console.
    *   Run: `mkvirtualenv --python=/usr/bin/python3.10 myenv`
    *   Run: `pip install flask mysql-connector-python python-dotenv`
    *   Back in the **Web** tab, enter path: `/home/YourUsername/.virtualenvs/myenv`

6.  **WSGI Configuration File:**
    *   Click the link to edit the WSGI file.
    *   Delete everything and paste this:
        ```python
        import sys
        import os
        
        # Add your project directory to the sys.path
        project_home = '/home/YourUsername/mysite'
        if project_home not in sys.path:
            sys.path = [project_home] + sys.path
            
        # Set environment variables
        os.environ['SECRET_KEY'] = 'your-secret-key'
        os.environ['MYSQL_HOST'] = 'YourUsername.mysql.pythonanywhere-services.com'
        os.environ['MYSQL_USER'] = 'YourUsername'
        os.environ['MYSQL_PASSWORD'] = 'your-db-password'
        os.environ['MYSQL_DB'] = 'YourUsername$visitor_db'
        
        from app import create_app
        application = create_app()
        ```
    *   **Save** the file.

## Step 5: Connect Your Domain
1.  In the **Web** tab, locate **DNS setup**.
2.  It will give you a **CNAME** (e.g., `webapp-123456.pythonanywhere.com`).
3.  Log in to your **Domain Registrar** (GoDaddy, Namecheap, etc.).
4.  Go to DNS Settings.
5.  Create a **CNAME Record**:
    *   **Host/Name:** `www`
    *   **Value/Target:** `webapp-123456.pythonanywhere.com` (The value from PythonAnywhere)
6.  Back in PythonAnywhere **Web** tab, enter your domain name (e.g., `www.yourdomain.com`) in the "Domain name" field.

## Step 6: Enable HTTPS (Crucial for Camera!)
1.  In the **Web** tab, scroll to **Security**.
2.  Click **"Force HTTPS"**.
3.  PythonAnywhere will automatically provision a **Let's Encrypt SSL certificate** for your domain (this might take a few minutes after DNS propagates).
4.  **Reload** your web app (Green button at the top).

## Step 7: Done!
*   Visit `https://www.yourdomain.com`.
*   Your Visitor Portal is now live, secure, and ready to use!
