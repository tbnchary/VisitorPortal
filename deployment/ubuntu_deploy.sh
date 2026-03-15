#!/bin/bash
# automated_deploy.sh - Ubuntu 22.04+ Deployment Script for Visitor Management System
# Run with: sudo bash automated_deploy.sh

set -e # Exit immediately if a command exits with a non-zero status

# ================= Configuration =================
APP_NAME="visitorportal"
REPO_URL="https://github.com/tbnchary/VisitorPortal.git"
CLONE_DIR="/var/www/$APP_NAME"
DB_USER="visitor_admin"
DB_PASS="SecurePass123!" # Change this!
DB_NAME="visitor_db"
SECRET_KEY=$(openssl rand -hex 32)
# =================================================

echo "================================================="
echo " Starting Full Ubuntu Deployment for "$APP_NAME" "
echo "================================================="

# 1. Update system & install dependencies
echo "[1/7] Installing System Dependencies..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev build-essential mysql-server nginx git pkg-config default-libmysqlclient-dev

# 2. Setup MySQL Database natively on this server
echo "[2/7] Configuring Local MySQL Database..."
sudo systemctl start mysql
sudo systemctl enable mysql
# Securely setup DB ignoring errors if user already exists
sudo mysql -e "CREATE DATABASE IF NOT EXISTS $DB_NAME;"
sudo mysql -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
sudo mysql -e "ALTER USER '$DB_USER'@'localhost' IDENTIFIED WITH mysql_native_password BY '$DB_PASS';"
sudo mysql -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

# 3. Clone / Pull Repository
echo "[3/7] Cloning Application Code..."
if [ -d "$CLONE_DIR" ]; then
    echo "Directory exists. Updating codebase..."
    cd $CLONE_DIR
    sudo git pull origin main
else
    sudo mkdir -p /var/www
    cd /var/www
    sudo git clone $REPO_URL $APP_NAME
    cd $CLONE_DIR
fi

# Ensure correct permissions
sudo chown -R $USER:www-data $CLONE_DIR
sudo chmod -R 775 $CLONE_DIR

# 4. Create Virtual Environment & Install Python packages
echo "[4/7] Setting up Python Environment..."
python3 -m venv venv
source venv/bin/activate
pip install wheel gunicorn
pip install -r requirements.txt

# 5. Create the .env configuration file
echo "[5/7] Writing Environment Configuration (.env)..."
cat &lt;&lt;EOF &gt; $CLONE_DIR/.env
SECRET_KEY=$SECRET_KEY
MYSQL_HOST=localhost
MYSQL_USER=$DB_USER
MYSQL_PASSWORD=$DB_PASS
MYSQL_DB=$DB_NAME
EOF

# 6. Create Systemd Service for Gunicorn (Runs app in background 24/7)
echo "[6/7] Creating Systemd Service..."
cat &lt;&lt;EOF | sudo tee /etc/systemd/system/$APP_NAME.service
[Unit]
Description=Gunicorn instance to serve $APP_NAME
After=network.target

[Service]
User=$USER
Group=www-data
WorkingDirectory=$CLONE_DIR
Environment="PATH=$CLONE_DIR/venv/bin"
EnvironmentFile=$CLONE_DIR/.env
ExecStart=$CLONE_DIR/venv/bin/gunicorn --workers 3 --bind unix:$CLONE_DIR/$APP_NAME.sock -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl start $APP_NAME
sudo systemctl enable $APP_NAME

# 7. Configure Nginx Reverse Proxy (Handles Web Traffic)
echo "[7/7] Configuring Nginx Web Server..."
cat &lt;&lt;EOF | sudo tee /etc/nginx/sites-available/$APP_NAME
server {
    listen 80;
    server_name _; # Accepts any IP/Domain

    location / {
        include proxy_params;
        proxy_pass http://unix:$CLONE_DIR/$APP_NAME.sock;
    }
}
EOF

# Enable Nginx Site & Remove Default
sudo ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
sudo ufw allow 'Nginx Full'

echo "================================================="
echo "             DEPLOYMENT COMPLETE!                "
echo "================================================="
echo "Your application is now live!"
echo "- App Directory: $CLONE_DIR"
echo "- Database Info: User=$DB_USER | DB=$DB_NAME"
echo "- To check status later run: sudo systemctl status $APP_NAME"
echo ""
echo "Access the app by typing your Server's IP address into a web browser!"
