from waitress import serve
from app import create_app
import os
import socket

app = create_app()

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == "__main__":
    ipv4 = get_ip()
    port = 8080
    
    print("\n" + "="*70)
    print("🚀 VISITOR PORTAL - PRODUCTION SERVER (WINDOWS)")
    print("="*70)
    print(f"\n✅ Server is running safely on Waitress (Production WSGI)")
    print(f"\n🌐 Local Network Access:")
    print(f"   http://{ipv4}:{port}")
    print(f"\n🌍 Internet Access (Once Domain is Configured):")
    print(f"   http://YOUR_DOMAIN.COM:{port}")
    print("\n" + "="*70 + "\n")
    
    serve(app, host='0.0.0.0', port=port, threads=6)
