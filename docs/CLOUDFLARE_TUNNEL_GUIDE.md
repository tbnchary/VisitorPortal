# 🚇 Host on Your PC with Cloudflare Tunnel (Free & Secure)

This is the **best way** to host the website on your **local Windows computer** and access it via **your custom domain** (e.g., `visitor-portal.com`), without opening router ports or exposing your IP.

**Prerequisites:**
1.  A Cloudflare Account (Free).
2.  Your Domain added to Cloudflare (Change your Name Servers to Cloudflare's).

---

## Step 1: Install Cloudored (The Tunnel)
1.  Download `cloudflared-windows-amd64.exe` from [Cloudflare Downloads](https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe).
2.  Rename it to `cloudflared.exe`.
3.  Move it to a folder, e.g., `C:\cloudflared\`.
4.  Open Command Prompt (Admin) and go to that folder:
    ```cmd
    cd C:\cloudflared\
    ```

## Step 2: Login & Create Tunnel
1.  Login to Cloudflare:
    ```cmd
    cloudflared login
    ```
    *(A browser window will open. Select your domain to authorize.)*

2.  Create a tunnel (lets call it `visitor-tunnel`):
    ```cmd
    cloudflared tunnel create visitor-tunnel
    ```
    *(Copy the **Tunnel ID** shown in the output, e.g., `a1b2c3d4...`)*

## Step 3: Route Domain to Tunnel
Tell Cloudflare to send traffic for `visitor-portal.com` to this tunnel:
```cmd
cloudflared tunnel route dns visitor-tunnel visitor-portal.com
```
*(Replace `visitor-portal.com` with your actual domain)*

## Step 4: Configure the Tunnel
Create a file named `config.yml` in `C:\cloudflared\` (or `C:\Users\YourUser\.cloudflared\`):
```yaml
tunnel: YOUR_TUNNEL_ID_HERE
credentials-file: C:\Users\YourUser\.cloudflared\YOUR_TUNNEL_ID_HERE.json

ingress:
  - hostname: visitor-portal.com
    service: http://localhost:8080
  - service: http_status:404
```

## Step 5: Run It!
1.  **Start your Visitor Portal** (in a separate terminal):
    ```cmd
    python serve.py
    ```
    *(Ensure it's running on port 8080)*

2.  **Start the Tunnel**:
    ```cmd
    cloudflared tunnel run visitor-tunnel
    ```

## Step 6: Verify
Go to `https://visitor-portal.com`.
Cloudflare handles the SSL (HTTPS) automatically. Your local app is now live on the internet!
