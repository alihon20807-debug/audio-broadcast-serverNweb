import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            extra_http_headers={"ngrok-skip-browser-warning": "true"}
        )
        page = await context.new_page()
        
        # Monitor console logs
        page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
        page.on("pageerror", lambda err: print(f"PAGE ERROR: {err}"))
        
        url = "https://mathilda-odious-southerly.ngrok-free.dev"
        print(f"Navigating to {url}...")
        try:
            await page.goto(url, timeout=30000)
            await asyncio.sleep(5) # Wait for JS to run
            
            status_text = await page.inner_text("#status-text")
            print(f"Status Text: {status_text}")
            
            await page.screenshot(path="debug_status.png")
            print("Screenshot saved to debug_status.png")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
