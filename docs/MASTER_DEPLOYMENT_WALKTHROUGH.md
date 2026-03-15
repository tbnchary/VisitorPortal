# 🚀 Ultimate Step-by-Step Guide: Deploy to Your Custom Domain

This is the definitive guide to taking your code and making it live at `https://yourdomain.com`.

**Prerequisites:**
1.  **A Domain Name** (bought from GoDaddy, Namecheap, etc.).
2.  **A Cloud Server (VPS)**. (Recommended: DigitalOcean, Vultr, or Linode - Ubuntu 22.04).
3.  **5 Minutes**.

---

## Phase 1: Point Your Domain (DNS)
*Before touching the server, tell the internet where your domain lives.*

1.  Log in to your **Domain Registrar**.
2.  Go to **DNS Settings** (or "Manage DNS").
3.  Find the **Records** section.
4.  **Create an 'A' Record**:
    *   **Type**: `A`
    *   **Host/Name**: `@` (represents `yourdomain.com`)
    *   **Value/IP**: `YOUR_SERVER_IP_ADDRESS` (e.g., `164.92.xxx.xxx`)
    *   **TTL**: Automatic/1 Hour.
5.  *(Optional)* **Create a 'CNAME' Record**:
    *   **Type**: `CNAME`
    *   **Host/Name**: `www`
    *   **Value**: `yourdomain.com`
6.  **Save**. (It may take a few minutes to propagate).

---

## Phase 2: Prepare the Server
*Connect to your new server to install the engine.*

1.  Open your terminal (or Putty) and SSH in:
    ```bash
    ssh root@YOUR_SERVER_IP
    ```
2.  **Update & Install Essentials**:
    ```bash
    apt update && apt upgrade -y
    apt install -y nginx python3-pip python3-venv mysql-server certbot python3-certbot-nginx git
    ```

---

## Phase 3: Setup the Database
*Create the place where visitors are stored.*

1.  Secure MySQL:
    ```bash
    mysql_secure_installation
    # Answer 'Y' to everything. Set a strong ROOT password.
    ```
2.  Create App Database & User:
    ```bash
    mysql -u root -p
    ```
    *(Enter the root password you just set)*
    ```sql
    CREATE DATABASE visitor_db;
    CREATE USER 'visitor_user'@'localhost' IDENTIFIED BY 'STRONG_PASSWORD';
    GRANT ALL PRIVILEGES ON visitor_db.* TO 'visitor_user'@'localhost';
    FLUSH PRIVILEGES;
    EXIT;
    ```

---

## Phase 4: Deploy the App
*Move your code to the server.*

1.  **Create Folder**:
    ```bash
    mkdir -p /var/www/visitor_portal
    ```
2.  **Upload Code**:
    *   *Option A (Git)*: `git clone https://github.com/your/repo.git /var/www/visitor_portal`
    *   *Option B (SFTP)*: Use FileZilla to drag-drop files into that folder.
3.  **Install Python Dependencies**:
    ```bash
    cd /var/www/visitor_portal
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install gunicorn mysql-connector-python
    ```
4.  **Configure Environment**:
    ```bash
    nano .env
    ```
    Paste this (Update password!):
    ```ini
    SECRET_KEY=change_this_to_something_random
    MYSQL_HOST=localhost
    MYSQL_USER=visitor_user
    MYSQL_PASSWORD=STRONG_PASSWORD
    MYSQL_DB=visitor_db
    ```
    *(Save: Ctrl+O, Enter, Ctrl+X)*

---

## Phase 5: Go Live (Nginx + Gunicorn)
*Connect the web server to the internet.*

1.  **Setup Gunicorn Service** (Keeps app running):
    *   Copy the service file I made for you:
        ```bash
        cp deployment/visitor_portal.service /etc/systemd/system/
        ```
    *   Start it:
        ```bash
        systemctl start visitor_portal
        systemctl enable visitor_portal
        ```

2.  **Setup Nginx** (Handles domain traffic):
    *   Copy the config file I made for you:
        ```bash
        cp deployment/nginx_visitor_portal /etc/nginx/sites-available/visitor_portal
        ```
    *   **Edit it to add your domain**:
        ```bash
        nano /etc/nginx/sites-available/visitor_portal
        ```
        Change `server_name YOUR_DOMAIN_OR_IP;` to `server_name yourdomain.com www.yourdomain.com;`.
    *   Activate it:
        ```bash
        ln -s /etc/nginx/sites-available/visitor_portal /etc/nginx/sites-enabled/
        rm /etc/nginx/sites-enabled/default
        systemctl restart nginx
        ```

---

## Phase 6: Secure with HTTPS (The Magic Step)
*Make the green lock appear and Enable Camera.*

1.  Run Certbot:
    ```bash
    certbot --nginx -d yourdomain.com -d www.yourdomain.com
    ```
2.  Select `2` (Redirect) if asked, to force HTTPS.

---

## 🎉 DONE!
Go to `https://yourdomain.com`.
Your professional Visitor Portal is live, secure, and ready for the world.
