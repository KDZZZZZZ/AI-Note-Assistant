import subprocess
import os
import threading

def install_backend_dependencies():
    print("Installing backend dependencies...")
    subprocess.run(["pip", "install", "-r", "backend/requirements.txt"], check=True)

def install_frontend_dependencies():
    print("Installing frontend dependencies...")
    subprocess.run(["npm", "install"], cwd="my-app", shell=True, check=True)

def run_backend():
    print("Starting backend...")
    return subprocess.Popen(["python", "app.py"], cwd="backend")

def run_frontend():
    print("Starting frontend...")
    return subprocess.Popen(["npm", "run", "dev"], cwd="my-app", shell=True)

if __name__ == "__main__":
    install_backend_dependencies()
    install_frontend_dependencies()

    backend_process = run_backend()
    frontend_process = run_frontend()

    try:
        # Wait for processes to terminate, or catch KeyboardInterrupt
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        backend_process.terminate()
        frontend_process.terminate()
        backend_process.wait() # Wait for processes to actually terminate
        frontend_process.wait()
    finally:
        print("Servers shut down.")