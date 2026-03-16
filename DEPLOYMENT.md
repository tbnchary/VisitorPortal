# Visitor Management System - Deployment Guide

This document outlines the step-by-step procedure to deploy the Visitor Management System from a local environment (using XAMPP/localhost) to a live production environment using **GitHub**, **Vercel** (for web hosting), and **Aiven** (for cloud MySQL database).

---

## 🏗️ Architecture Overview
*   **Frontend/Backend Engine:** Python Flask 
*   **Web Hosting:** Vercel (Serverless Functions)
*   **Database:** Aiven Free MySQL Cloud Database
*   **Version Control:** GitHub

---

## 🛠️ Step 1: Codebase Preparation for Vercel

Vercel requires specific configuration files to know how to install dependencies and run a Python Flask application.

1.  **`requirements.txt`**: Ensure all required Python packages (like `Flask`, `mysql-connector-python`, etc.) are listed.
2.  **`vercel.json`**: Create this file in the root directory to define the build environment and routing.
    ```json
    {
      "version": 2,
      "builds": [
        {
          "src": "wsgi.py",
          "use": "@vercel/python"
        }
      ],
      "routes": [
        {
          "src": "/(.*)",
          "dest": "wsgi.py"
        }
      ]
    }
    ```
3.  **`wsgi.py`**: Create this entry-point file in the root directory. This explicitly passes the Flask `app` object to Vercel.
    ```python
    from app import create_app

    app = create_app()

    if __name__ == "__main__":
        app.run()
    ```
4.  **Database Connection Adjustments (`app/db.py`)**: Ensure your database connection uses environment variables instead of hardcoded `root` and `localhost` configurations, accommodating the cloud environment.

---

## ☁️ Step 2: Cloud Database Setup (Aiven)

Since serverless applications cannot connect to local databases (like XAMPP's `localhost`), you need a cloud-hosted MySQL database.

1.  Go to [Aiven.io](https://aiven.io/) and create a free account (can log in with GitHub).
2.  Create a new **Free MySQL Service**.
3.  Once provisioned, note down the following **Connection Details**:
    *   **Host URL** (e.g., `mysql-xxxx...aivencloud.com`)
    *   **Port** (e.g., `17551`)
    *   **User** (default is usually `avnadmin`)
    *   **Password** 
    *   **Database Name** (default is usually `defaultdb`)

---

## 🐙 Step 3: Push to GitHub

Vercel connects directly to GitHub to deploy your code automatically whenever you push new changes.

1.  Initialize git in your project if you haven't already: `git init`
2.  Add all files: `git add .`
3.  Commit changes: `git commit -m "Initial Vercel deployment setup"`
4.  Push the repository to your GitHub account.

---

## 🚀 Step 4: Deploy on Vercel

1.  Log in to [Vercel](https://vercel.com/) (you can use your GitHub account).
2.  Click **Add New... -> Project**.
3.  Import your `VisitorPortal` repository from GitHub.
4.  In the configuration screen, open the **Environment Variables** section.
5.  Add the exact credentials you got from Aiven in Step 2:
    *   `MYSQL_HOST`: (Your Aiven Host)
    *   `MYSQL_PORT`: (Your Aiven Port)
    *   `MYSQL_USER`: (Your Aiven User)
    *   `MYSQL_PASSWORD`: (Your Aiven Password)
    *   `MYSQL_DB`: (Your Aiven Database Name)
    *   `SECRET_KEY`: (A random secure string for Flask sessions)
6.  Click **Deploy**.

---

## 🗄️ Step 5: Data Migration (Local to Cloud)

After Vercel deploys the app, it is connected to a brand-new, completely empty database. To preserve your existing local data, run the included Python migration script.

1.  Ensure your local XAMPP MySQL server is running.
2.  Open the file `migrate_db.py`.
3.  Temporarily ensure the `remote_db` credentials match your live Aiven database (Host, User, Password, Port).
    *   *(Note: Never commit your real passwords to GitHub. Use placeholders like `YOUR_AIVEN_PASSWORD` in the code after migration).*
4.  Run the script from your terminal:
    ```bash
    python migrate_db.py
    ```
5.  This script will automatically:
    *   Connect to both `localhost` and the live `aivencloud` connection.
    *   Reconstruct the exact table schemas (users, visitors, etc.).
    *   Clone every single row of data from your local computer into the live web database.

---

## ✅ Step 6: Final Verification

1.  Go to the URL provided by Vercel (e.g., `https://visitor-portal-iota.vercel.app/`).
2.  The login screen should appear.
3.  Because the `migrate_db.py` script ran successfully, you can now log in using the exact same username and password you were using on your local version.

🎉 **Deployment is now complete!** Any subsequent code changes pushed to the `main` branch on GitHub will automatically be deployed to Vercel within minutes.
