# 🌐 Connect Your Custom Domain (Self-Hosting Guide)

Since you want to use your **own domain** (e.g., `visitor-portal.com`) and host it exactly where you want (on your own VPS or this computer), follow these specific steps.

## Phase 1: DNS Configuration (Connect Domain to Server)

1.  **Find your Server's Public IP**:
    *   If hosted on a VPS (DigitalOcean, AWS), copy the IP from their dashboard (e.g., `143.22.xx.xx`).
    *   If hosting **at home/office (Windows)**, google "What is my IP" to get your Public IP. *Note: You will need to set up "Port Forwarding" on your router for Port 80 and 443 pointing to this computer's local IP.*

2.  **Login to your Domain Registrar**:
    *   Go to where you bought your domain (GoDaddy, Namecheap, Google Domains).
    *   Find **DNS Settings** or **DNS Management**.

3.  **Create an 'A' Record**:
    *   **Type**: `A`
    *   **Name/Host**: `@` (means the root domain, e.g., `yourdomain.com`) or `portal` (for `portal.yourdomain.com`).
    *   **Value/Points to**: `YOUR_PUBLIC_IP_ADDRESS`
    *   **TTL**: `1 Hour` or `3600`.
    *   *Click Save.*

---

## Phase 2: Production Server Setup (Windows)

We have created a new production-ready script (`serve.py`) that uses **Waitress**. This is much more stable and secure than the standard `run.py` for serving traffic to the internet.

1.  **Install Waitress**:
    ```powershell
    pip install waitress
    ```

2.  **Run the Production Server**:
    ```powershell
    python serve.py
    ```

---

## Phase 3: HTTPS (SSL) - Mandatory for Camera Access

Browsers **will block camera access** if your site is not `https://`. Connecting a domain is not enough; you need a Certificate.

### Option A: Using a Reverse Proxy (Recommended for Windows)
The professional way is to run **Nginx for Windows** in front of your Python app.
1.  Download Nginx for Windows.
2.  Configure `nginx.conf` to proxy pass to `http://127.0.0.1:8080`.
3.  Use a tool like **Win-Acme** to automatically generate Let's Encrypt certificates for Nginx on Windows.

### Option B: Using a Tunnel (Easiest for Local Windows)
If setting up Nginx/SSL on Windows is too complex, use **Ngrok** to instantly give you a secure Domain URL with valid SSL.
1.  Download `ngrok`.
2.  Run your app: `python serve.py`
3.  Run ngrok: `ngrok http 8080 --domain=your-custom-domain.com`
    *(Requires Ngrok paid plan for custom domains, or use their free random URLs which support HTTPS automatically)*

### Option C: Linux VPS (Best for "Set and Forget")
If you deploy to a Linux server (using the `DEPLOYMENT_GUIDE.md` provided earlier), getting SSL is just one command:
```bash
certbot --nginx -d your-domain.com
```
This is why Linux is preferred for production web apps.

---

## Summary Checklist

- [ ] **DNS**: A Record points to Public IP.
- [ ] **Network**: Port 80/443 forwarded to server (if local).
- [ ] **Server**: Running `python serve.py` (Waitress).
- [ ] **Security**: SSL Certificate installed (via Nginx/Certbot or Tunnel).
