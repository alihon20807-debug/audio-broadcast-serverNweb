import asyncio
import socket
import time
import multiprocessing
import sys
import os
from playwright.async_api import async_playwright

# Add parent directory to sys.path to allow importing 'app.py'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import main as boot_server

# The current WAN URL for testing
WAN_URL = "https://mathilda-odious-southerly.ngrok-free.dev"


async def do_stuff(page):
    """
    Verifies that the site is loaded and connected to the backend.
    Checks the status indicator and basic UI elements.
    """
    url = page.url
    print(f"  [Verify] Checking {url}...")
    try:
        # Wait for the main status element to appear
        await page.wait_for_selector("#status-text", timeout=15000)

        # Wait for the status to transition from 'Hardware Offline' to a connected state
        # Possible connected statuses: "Connected — Tap Start", "Stabilizing…", "System Ready"
        connected = False
        for _ in range(30):  # Check for 15 seconds
            status_text = await page.inner_text("#status-text")
            if any(
                s in status_text
                for s in ["Connected", "Stabilizing", "Ready", "System"]
            ):
                connected = True
                break
            await asyncio.sleep(0.5)

        if connected:
            print(f"  [Page {url}] CONFIRMED LOADED: {status_text}")
            return "Pass"
        else:
            current = await page.inner_text("#status-text")
            print(f"  [Page {url}] FAILED: Status remains '{current}'")
            return "Fail"
    except Exception as e:
        print(f"  [Page {url}] ERROR during verification: {str(e)}")
        return "Error"


async def launch_4_browsers(url: str):
    """
    Launches 4 browser instances simultaneously, navigating each to the target URL.
    Includes configuration to bypass ngrok warnings and allow audio autoplay.
    """
    async with async_playwright() as p:
        # Launching browsers with autoplay enabled
        launch_tasks = []
        for i in range(4):
            launch_tasks.append(
                p.chromium.launch(
                    headless=False, args=["--autoplay-policy=no-user-gesture-required"]
                )
            )

        browsers = await asyncio.gather(*launch_tasks)
        contexts = []
        pages = []

        # Setup each browser context with ngrok bypass headers
        setup_tasks = []
        for i, browser in enumerate(browsers):
            print(f"Setting up instance {i + 1}...")
            context = await browser.new_context(
                extra_http_headers={"ngrok-skip-browser-warning": "true"}
            )
            contexts.append(context)
            page = await context.new_page()
            pages.append(page)
            setup_tasks.append(page.goto(url))

        # Navigate all pages concurrently
        await asyncio.gather(*setup_tasks)
        print(f"All 4 browsers navigated to {url}. Starting verification...")

        # Perform site confirmation for each page
        results = await asyncio.gather(*[do_stuff(page) for page in pages])

        if all(r == "Pass" for r in results):
            print("\nSUCCESS: All 4 site instances are loaded and connected.")
        else:
            print(f"\nWARNING: Some instances failed verification: {results}")

        print(
            "\nKeep-alive: Browsers will remain open until you stop this script (Ctrl+C)."
        )
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            print("Closing browsers...")
            await asyncio.gather(*[b.close() for b in browsers])


def is_server_running(host="127.0.0.1", port=5000):
    """Check if the server is already running on the given port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    server_process = None
    try:
        if is_server_running():
            print("Server is already running. Skipping boot.")
        else:
            print("Server not detected. Starting server...")
            server_process = multiprocessing.Process(target=boot_server, daemon=True)
            server_process.start()
            # Give the server a few seconds to initialize
            for _ in range(10):
                if is_server_running():
                    print("Server started successfully.")
                    break
                time.sleep(1)
            else:
                print("Warning: Server start-up timed out.")

        asyncio.run(launch_4_browsers(WAN_URL))
    except KeyboardInterrupt:
        print("\nShutdown requested by user.")
    finally:
        if server_process and server_process.is_alive():
            print("Terminating server process...")
            server_process.terminate()
            server_process.join(timeout=5)
            if server_process.is_alive():
                server_process.kill()
            print("Server process shut down.")
