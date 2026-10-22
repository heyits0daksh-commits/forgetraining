"""Start FORGE so your phone can open it (same Wi-Fi).

    python run_phone.py

Then open the address it prints in your phone's browser.
"""
import socket
import subprocess
import sys

PORT = 8000


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no data is sent; just picks the Wi-Fi interface
        return s.getsockname()[0]
    except OSError:
        return "YOUR-COMPUTER-IP"
    finally:
        s.close()


print("\n" + "=" * 50)
print("  FORGE is starting. On your phone, open:\n")
print(f"      http://{lan_ip()}:{PORT}\n")
print("  (phone and computer must be on the same Wi-Fi)")
print("=" * 50 + "\n")

subprocess.call([
    sys.executable, "-m", "uvicorn", "backend.main:app",
    "--host", "0.0.0.0", "--port", str(PORT),
])
