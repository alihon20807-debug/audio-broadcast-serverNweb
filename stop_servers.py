import os
import signal
import psutil

def kill_process_on_port(port):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == port:
                    print(f"Killing process {proc.info['name']} (PID: {proc.pid}) on port {port}")
                    proc.send_signal(signal.SIGTERM)
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

def kill_by_content(pattern):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            if pattern in cmdline and proc.pid != os.getpid():
                print(f"Killing process (PID: {proc.pid}): {cmdline}")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

if __name__ == "__main__":
    print("Stopping all project servers...")
    
    # Kill app.py
    kill_by_content("app.py")
    
    # Kill port 5000
    kill_process_on_port(5000)
    
    print("Cleanup complete.")
