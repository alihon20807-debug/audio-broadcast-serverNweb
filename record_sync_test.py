import asyncio
import os
import subprocess
import time
import wave
import numpy as np
import shutil
import http.client
from playwright.async_api import async_playwright

# Configuration
# Hybrid testing URLs (2 Local, 2 LAN, 2 WAN)
TEST_URLS = [
    "http://127.0.0.1:5000",
    "http://127.0.0.1:5000",
    "http://172.17.57.89:5000",
    "http://172.17.57.89:5000",
    "https://mathilda-odious-southerly.ngrok-free.dev",
    "https://mathilda-odious-southerly.ngrok-free.dev"
]
RECORD_SECONDS = 20 # Increased for WAN latency buffer
TMP_DIR = "tmp_sync"
REFERENCE_FILE = "reference.wav"
PRODUCTION_FILE = "prod_output.wav"

def save_wav(filename, data_float32, sr=44100):
    """Save raw float32 PCM data as a 16-bit WAV file."""
    # Normalize to prevent clipping (especially for the 6-tab mix)
    max_val = np.abs(data_float32).max()
    if max_val > 0:
        data_float32 = data_float32 / max_val
    
    # Convert to Int16
    data_int16 = (data_float32 * 32767).astype(np.int16)
    
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data_int16.tobytes())
    print(f"[MIX] Saved {filename}")

async def run_sync_test(num_tabs, output_filename):
    print(f"\n--- Starting Automated Sync Phase: {output_filename} ({num_tabs} tabs) ---")
    
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(TMP_DIR)

    async with async_playwright() as p:
        # Launch with bypass for insecure origins (needed for LAN IP AudioContext)
        browser = await p.chromium.launch(
            headless=True,
            args=[
                f"--unsafely-treat-insecure-origin-as-secure=http://172.17.57.89:5000"
            ]
        )
        # 0. Initialize context with bypass for ngrok interstitial
        context = await browser.new_context(
            extra_http_headers={
                "ngrok-skip-browser-warning": "true"
            }
        )
        # Initialize pages in parallel
        pages = await asyncio.gather(*(context.new_page() for _ in range(num_tabs)))
        
        # Assign URLs: Reference uses localhost, Production uses the hybrid list
        target_urls = ["http://127.0.0.1:5000"] * num_tabs if num_tabs == 1 else TEST_URLS
        
        print(f"[TEST] Navigating {num_tabs} tabs to target origins...")
        await asyncio.gather(*(pages[i].goto(target_urls[i]) for i in range(num_tabs)))
            
        # 1. Wait for Clock Sync in parallel (Robust for WAN latency)
        async def wait_for_sync(page, idx):
            while True:
                try:
                    # Check if telemetry object even exists yet
                    is_ready = await page.evaluate("typeof window.__sync_telemetry !== 'undefined'")
                    if is_ready:
                        offset = await page.evaluate("window.__sync_telemetry.serverOffset")
                        if offset != 0:
                            break
                except Exception:
                    # Silence common "page not loaded" errors during initial boot
                    pass
                await asyncio.sleep(1.0) # 1s poll is safer for WAN
            print(f"[TEST] Tab {idx+1} Clock Synced.")

        await asyncio.gather(*(wait_for_sync(page, i) for i, page in enumerate(pages)))

        # 2. Start Internal Recording on all tabs simultaneously
        print("[TEST] Starting parallel internal PCM recording...")
        await asyncio.gather(*(page.evaluate("startInternalRecording()") for page in pages))

        # 3. Trigger Play (Master tab)
        print("[TEST] Triggering Synchronized Playback...")
        # Note: We use the final tab as master to ensure everyone else is joined
        await pages[-1].click("#mainBtn")
        
        # 4. Wait for duration
        await asyncio.sleep(RECORD_SECONDS)
        
        # 5. Stop Recording and Upload simultaneously
        print("[TEST] Stopping and uploading recordings...")
        await asyncio.gather(*(page.evaluate("stopInternalRecording()") for page in pages))
            
        # 6. Wait for all files to arrive in tmp_sync
        print("[TEST] Waiting for uploads to complete...")
        max_wait = 30
        while len(os.listdir(TMP_DIR)) < num_tabs and max_wait > 0:
            await asyncio.sleep(1)
            max_wait -= 1
            
        await browser.close()

    # 7. Mix the raw files
    print(f"[MIX] Mixing {num_tabs} streams into {output_filename}...")
    combined_data = None
    
    files = os.listdir(TMP_DIR)
    if not files:
        print("[ERROR] No recordings were uploaded.")
        return

    for filename in files:
        file_path = os.path.join(TMP_DIR, filename)
        with open(file_path, "rb") as f:
            raw_data = f.read()
            # Convert bytes back to Float32 array (interleaved 2-channel)
            data = np.frombuffer(raw_data, dtype=np.float32)
            
            if combined_data is None:
                combined_data = data.copy()
            else:
                # In-place sum the waveforms (reduced memory allocations)
                min_len = min(len(combined_data), len(data))
                combined_data[:min_len] += data[:min_len]
                # If the new chunk is longer, we truncate it (sync tests should be equal length)
                
    if combined_data is not None:
        save_wav(output_filename, combined_data)
    
    # Cleanup temp files
    shutil.rmtree(TMP_DIR)

async def main():
    # Start Flask Server
    print("[SERVER] Starting Flask app...")
    server_process = subprocess.Popen(
        ["python", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    
    # Wait for server boot (polling)
    print("[SERVER] Waiting for server to respond on http://127.0.0.1:5000...")
    max_retries = 20
    while max_retries > 0:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 5000)
            conn.request("GET", "/")
            res = conn.getresponse()
            if res.status == 200:
                print("[SERVER] Online!")
                break
        except Exception:
            pass
        max_retries -= 1
        time.sleep(0.5)
    
    try:
        # Phase 1: Reference (1 tab)
        await run_sync_test(1, REFERENCE_FILE)
        
        # Phase 2: Production (6 tabs)
        await run_sync_test(6, PRODUCTION_FILE)
        
    finally:
        print("[SERVER] Shutting down...")
        if os.name == 'nt':
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(server_process.pid)])
        else:
            server_process.terminate()

if __name__ == "__main__":
    asyncio.run(main())
