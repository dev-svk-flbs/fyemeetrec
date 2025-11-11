import subprocess
import sys

print("ULTRA MINIMAL TEST")
print(f"My PID would be visible in process list")

process = subprocess.Popen([sys.executable, "hotkey_listener.py"])
print(f"Started hotkey with PID: {process.pid}")

input("Press Enter to exit...")
process.terminate()