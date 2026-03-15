from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    port = 5001 # Changed to 5001 to avoid conflicts
    
    print("\n" + "="*70)
    print("🚀 VISITOR PORTAL STARTING (PLAIN HTTP MODE)")
    print("="*70)
    print("\n📱 Access from this computer:")
    print(f"   http://localhost:{port}")
    print(f"   http://127.0.0.1:{port}")
    print("\n🌐 Access from other devices on network:")
    print(f"   http://YOUR_IP_ADDRESS:{port}")
    print("\n📸 NOTE: Camera features require HTTPS.")
    print("   To enable HTTPS, use: app.run(..., ssl_context='adhoc')")
    print("="*70 + "\n")
    
    # Starting in PLAIN HTTP for compatibility
    app.run(host='0.0.0.0', debug=True, port=port)
