# 🌐 The "No Server" Solution (Cloudflare Tunnel)

Since you **have a domain** but **no server**, we will host the website **directly from your computer** (the one you are using right now) and connect it to the internet securely using a **free Cloudflare Tunnel**.

**This means:**
1.  Your computer acts as the server.
2.  Your domain (e.g., `visitor-portal.com`) will point to your computer.
3.  Cloudflare handles the HTTPS security for you (Essential for camera access).
4.  **Note:** Your computer must stay ON for the specific website to be accessible.

---

## Step 1: Get Cloudflared (The Connector)
1.  **Download** the Windows tool: [cloudflared-windows-amd64.exe](https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe).
2.  **Move it** to a simple folder, like `C:\Cloudflare`.
3.  **Rename** the file to just `cloudflared.exe`.

## Step 2: Login to Cloudflare
1.  Open **Command Prompt** as Administrator.
2.  Go to the folder:
    ```cmd
    cd C:\Cloudflare
    ```
3.  Login:
    ```cmd
    cloudflared login
    ```
    *(A browser window will open. Select your domain to authorize it.)*

## Step 3: Create the Secure Tunnel
1.  Create a new tunnel (let's name it `my-pc`):
    ```cmd
    cloudflared tunnel create my-pc
    ```
    *(Copy the **Tunnel ID** shown in the output, e.g., `a1b2c3d4-5678...`)*

## Step 4: Configure the Tunnel
1.  In `C:\Users\YOUR_USERNAME\.cloudflared\`, create a new file named `config.yml`.
2.  Paste this content (replace `YOUR_TUNNEL_ID` with the ID from Step 3):

    ```yaml
    tunnel: YOUR_TUNNEL_ID
    credentials-file: C:\Users\YOUR_USERNAME\.cloudflared\YOUR_TUNNEL_ID.json

    ingress:
      - hostname: YOUR_DOMAIN.COM
        service: http://localhost:8080
      - service: http_status:404
    ```
    *(Replace `YOUR_DOMAIN.COM` with your actual domain name).*
    *(Replace `YOUR_USERNAME` with your actual Windows username).*

## Step 5: Route the Domain
Tell Cloudflare to send traffic for your domain to this tunnel:
```cmd
cloudflared tunnel route dns my-pc YOUR_DOMAIN.COM
```
*(Replace `YOUR_DOMAIN.COM` with your actual domain name).*

## Step 6: Run Everything!

**Terminal 1 (Run the Website):**
Go to your project folder (`visitor_portal...`) and run:
```cmd
python serve.py
```

**Terminal 2 (Run the Tunnel):**
Go to `C:\Cloudflare` and run:
```cmd
cloudflared tunnel run my-pc
```

---

## 🎉 You are Live!
Go to `https://YOUR_DOMAIN.COM` on any device (phone, laptop) anywhere in the world.
-   The site loads from your computer!
-   The **Camera** works (because Cloudflare adds HTTPS).
-   It's free!
