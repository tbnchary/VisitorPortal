# ☁️ Deploying on Google or Microsoft (Alternatives)

You asked about **Google** (Gmail) or **Microsoft** (Outlook).
While **Gmail** and **Outlook** are just email services (they cannot host websites), their parent companies offer powerful cloud hosting platforms that allow you to deploy your app without managing a server.

Here are the two best "Big Tech" alternatives to running it on your own PC.

---

## Option 1: Google Cloud Platform (App Engine)
*Best for: "I want it running on Google's infrastructure."*

**Price:** Free tier available, then pay-as-you-go.
**Difficulty:** Medium (Requires installing a tool).

**Steps:**
1.  Go to [console.cloud.google.com](https://console.cloud.google.com/) and sign in with your **Gmail**.
2.  **Create a New Project** (e.g., "visitor-portal").
3.  **Install the "Google Cloud SDK"** on your computer:
    *   Download and run the installer from Google.
4.  **Add a configuration file**:
    *   Create a file named `app.yaml` in your project folder with this content:
        ```yaml
        runtime: python310
        entrypoint: gunicorn -b :$PORT wsgi:app
        
        env_variables:
          SECRET_KEY: "your-secret-key"
          MYSQL_HOST: "your-database-ip"  # You need a cloud DB for this
          MYSQL_USER: "root"
          MYSQL_PASSWORD: "password"
        ```
5.  **Deploy**:
    *   Open terminal in your project folder.
    *   Run: `gcloud init` (Login and select project).
    *   Run: `gcloud app deploy`.
6.  **Done!** Your app runs at `https://visitor-portal.uc.r.appspot.com`.
7.  **Custom Domain**: In the Google Cloud Console > App Engine > Settings > Custom Domains, you can add `your-domain.com`.

---

## Option 2: Microsoft Azure (App Service)
*Best for: "I want it running on Microsoft's infrastructure."*

**Price:** Free tier (F1) is limited; Basic tier costs money.
**Difficulty:** Medium/High (Complex interface).

**Steps:**
1.  Go to [portal.azure.com](https://portal.azure.com/) and sign in with your **Outlook/Microsoft** account.
2.  Search for **"App Services"** and click **Create**.
3.  **Basics**:
    *   Subscription: Free Trial / Pay-As-You-Go.
    *   Name: `visitor-portal` (This makes `visitor-portal.azurewebsites.net`).
    *   Publish: Code.
    *   Runtime stack: Python 3.10.
    *   OS: Linux.
4.  **Review + Create**.
5.  **Deploy Code**:
    *   Install the **"Azure App Service"** extension in VS Code.
    *   Right-click your project folder in VS Code -> "Deploy to Web App".
    *   Select the app you just created.
6.  **Custom Domain**:
    *   In Azure Portal > App Service > Custom Domains, add `your-domain.com` (Requires paid tier).

---

## 🏆 Recommendation: Stick to "PythonAnywhere" or "Cloudflare Tunnel"

*   **Google & Azure** are powerful but **complicated** for a simple app. They require setting up a separate Cloud Database (Cloud SQL) which costs extra money ($10-50/mo) or is tricky to configure.
*   **PythonAnywhere** (The first alternative I gave you) is much simpler: it includes the Database + Hosting in one $5/mo package.
*   **Your PC + Cloudflare Tunnel** (Technical "No Server" option) is **Free** and gives you full control.

### Summary of Choices:
1.  **Google/Azure**: Professional, scalable, but **complex & expensive** (Database costs).
2.  **PythonAnywhere**: **Easiest** cloud option ($5/mo).
3.  **Your PC + Cloudflare**: **Free**, but PC must stay on.
