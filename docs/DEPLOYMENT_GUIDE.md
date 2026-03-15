# 🚀 Deployment Guide: Visitor Portal

This guide provides step-by-step instructions for deploying your Visitor Portal application to your own domain using a Linux VPS (Virtual Private Server) like DigitalOcean, Linode, AWS EC2, or Vultr.

## Prerequisites

1.  **A Domain Name** (e.g., `yourcompany.com` or `portal.yourcompany.com`)
    *   Point the A Record of your domain to your server's IP address.
2.  **A Linux Server (Ubuntu 22.04 or 24.04 recommended)**
    *   Root access via SSH.
3.  **Basic knowledge of terminal commands.**

---

## 1. Initial Server Setup & Updates

Connect to your server via SSH:
```bash
ssh root@YOUR_SERVER_IP
```

Update the system packages:
```bash
apt update && apt upgrade -y
```

Install necessary dependencies (Python, MySQL, Nginx, Certbot):
```bash
apt install -y python3-pip python3-venv python3-dev libmysqlclient-dev build-essential nginx git certbot python3-certbot-nginx mysql-server
```

---

## 2. Configure Database (MySQL)

Secure your MySQL installation and create a database/user:

```bash
mysql_secure_installation
# Follow the prompts to set a root password and remove test dbs.
```

Log in to MySQL:
```bash
mysql -u root -p
```

Run the following SQL commands:
```sql
CREATE DATABASE visitor_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'visitor_user'@'localhost' IDENTIFIED BY 'YOUR_SECURE_PASSWORD';
GRANT ALL PRIVILEGES ON visitor_db.* TO 'visitor_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## 3. Deployment Directory Setup

Create a directory for your app:
```bash
mkdir -p /var/www/visitor_portal
cd /var/www/visitor_portal
```

**Option A: Upload Files via SFTP/SCP**
Use a tool like FileZilla or WinSCP to upload your project files to `/var/www/visitor_portal`.

**Option B: Clone from Git (Recommended)**
If your code is on GitHub/GitLab:
```bash
git clone https://github.com/yourusername/your-repo.git .
```

---

## 4. Python Environment Setup

Create a virtual environment:
```bash
python3 -m venv venv
```

Activate and install dependencies:
```bash
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

Create a `.env` file for your secrets:
```bash
nano .env
```
Paste the following (update with your actual values):
```bash
SECRET_KEY=super-secret-key-change-this
MYSQL_HOST=localhost
MYSQL_USER=visitor_user
MYSQL_PASSWORD=YOUR_SECURE_PASSWORD
MYSQL_DB=visitor_db
FLASK_ENV=production
```
Press `Ctrl+X`, then `Y`, then `Enter` to value.

---

## 5. Configure Gunicorn Service

We need Gunicorn to serve the Python app and Systemd to keep it running.

Copy the service file provided in your project:
```bash
cp deployment/visitor_portal.service /etc/systemd/system/
```

Verify the file content (ensure paths match your setup):
```bash
nano /etc/systemd/system/visitor_portal.service
```
*Make sure `User=root` or change it to a non-root user if you created one.*

Start and enable the service:
```bash
systemctl start visitor_portal
systemctl enable visitor_portal
systemctl status visitor_portal
```
*You should see "Active: active (running)".*

---

## 6. Configure Nginx (Reverse Proxy)

Nginx will handle incoming requests and SSL.

Copy the Nginx config provided in your project:
```bash
cp deployment/nginx_visitor_portal /etc/nginx/sites-available/visitor_portal
```

Edit the file to set your domain name:
```bash
nano /etc/nginx/sites-available/visitor_portal
```
Change `server_name YOUR_DOMAIN_OR_IP;` to your actual domain, e.g., `server_name portal.example.com;`.

Enable the site:
```bash
ln -s /etc/nginx/sites-available/visitor_portal /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t
# If test is successful:
systemctl restart nginx
```

---

## 7. Setup HTTPS (SSL) - Critical for Camera

Camera access requires HTTPS. We'll use Certbot (Let's Encrypt) for free SSL.

Run Certbot:
```bash
certbot --nginx -d portal.example.com
```
Follow the prompts. Certbot will automatically update your Nginx config to serve HTTPS.

---

## 8. Final Verification

1.  Open `https://portal.example.com` in your browser.
2.  Test the **Add Visitor** functionality.
3.  Test the **Camera** (browser should ask for permission securely).
4.  Check logs if anything fails:
    ```bash
    journalctl -u visitor_portal -f
    tail -f /var/log/nginx/error.log
    ```

---

## Alternative: Platform-as-a-Service (Heroku/Render)

If you prefer not to manage a server:

1.  Push your code to GitHub.
2.  Connect your repo to **Render.com** or **Heroku**.
3.  Add a **MySQL Database** service.
4.  Set Environment Variables (`MYSQL_HOST`, `MYSQL_USER`, etc.) in the dashboard.
5.  Deploy! The included `Procfile` (`web: gunicorn wsgi:app`) will handle the start command.
