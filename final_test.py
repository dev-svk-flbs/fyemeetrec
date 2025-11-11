import subprocess
import sys
import os
import textwrap
import tempfile
import time

def main():
    print(f"[LAUNCHER] PID: {os.getpid()}")
    print(f"[LAUNCHER] Executable: {sys.executable}")
    print(f"[LAUNCHER] CWD: {os.getcwd()}")
    print("[LAUNCHER] Creating dummy script...")

    # Create a temporary dummy script in a safe location
    dummy_code = textwrap.dedent("""
        import os, time, sys
        print(f"[DUMMY] PID: {os.getpid()}")
        print(f"[DUMMY] Parent PID: {os.getppid()}")
        print(f"[DUMMY] Executable: {sys.executable}")
        sys.stdout.flush()
        time.sleep(60)
    """)

    dummy_path = os.path.join(tempfile.gettempdir(), "dummy_test.py")
    with open(dummy_path, "w", encoding="utf-8") as f:
        f.write(dummy_code)

    print(f"[LAUNCHER] Dummy script written to: {dummy_path}")

    # Launch dummy safely
    try:
        process = subprocess.Popen(
            [sys.executable, dummy_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        )
    except Exception as e:
        print(f"[LAUNCHER] Failed to launch dummy: {e}")
        return

    print(f"[LAUNCHER] Started dummy with PID: {process.pid}")
    print("[LAUNCHER] Reading its output for verification...\n")

    # Read a few lines of output to confirm behavior
    try:
        for _ in range(3):
            line = process.stdout.readline()
            if not line:
                break
            print(f"[DUMMY OUTPUT] {line.strip()}")
    except Exception as e:
        print(f"[LAUNCHER] Could not read output: {e}")

    input("\n[LAUNCHER] Press Enter to terminate dummy and exit...")

    process.terminate()
    process.wait(timeout=5)
    print("[LAUNCHER] Dummy terminated. Exiting cleanly.")

if __name__ == "__main__":
    main()
