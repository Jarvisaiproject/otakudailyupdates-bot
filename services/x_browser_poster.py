import sys
import os
import time
import re

# Ensure root project directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright
from config import config
from database.memory import MemoryDB

class XBrowserPoster:
    """
    Automated Playwright Persistent Browser Poster for X (Twitter).
    Uses a persistent browser profile folder (.x_session) to stay logged into @OtakuUpdates106 24/7.
    """

    def __init__(self):
        self.session_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".x_session"))
        os.makedirs(self.session_dir, exist_ok=True)

    def setup_login(self):
        """
        Launches interactive Chromium window for initial login to @OtakuUpdates106.
        Saves session profile to .x_session directory.
        """
        print("[*] Launching browser profile for X (Twitter) Login...")
        print("[!] Please log in to your X account (@OtakuUpdates106) in the opened browser window.")
        print("[!] Once logged in and on the home page, press ENTER in this terminal.")

        with sync_playwright() as p:
            try:
                context = p.chromium.launch_persistent_context(self.session_dir, channel="msedge", headless=False, viewport={"width": 1280, "height": 800})
            except Exception:
                context = p.chromium.launch_persistent_context(self.session_dir, headless=False, viewport={"width": 1280, "height": 800})

            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://x.com/i/flow/login")

            input("\n===> Press ENTER after you have successfully logged into @OtakuUpdates106 on X... <===")

            print(f"[+] X Login Session saved successfully to persistent profile!")
            context.close()

    def post_tweet(self, text: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Posts tweet to X automatically using persistent browser profile.
        """
        print(f"[*] [Playwright Auto-Poster] Posting to X (@OtakuUpdates106)...")

        try:
            with sync_playwright() as p:
                try:
                    context = p.chromium.launch_persistent_context(self.session_dir, channel="msedge", headless=False, viewport={"width": 1280, "height": 800})
                except Exception:
                    context = p.chromium.launch_persistent_context(self.session_dir, headless=False, viewport={"width": 1280, "height": 800})

                page = context.pages[0] if context.pages else context.new_page()

                # Navigate to X Home
                page.goto("https://x.com/home", wait_until="domcontentloaded")
                time.sleep(5)

                # Check if redirected to login
                if "login" in page.url:
                    context.close()
                    msg = "X session expired or missing login. Run 'python services/x_browser_poster.py --login' to re-login."
                    MemoryDB.log_event("WARNING", "XBrowserPoster", msg)
                    return {"status": "draft", "message": msg}

                # Check if compose button on sidebar exists and click it
                try:
                    sidebar_post_btn = page.locator('a[href="/compose/post"], button[data-testid="SideNav_NewTweet_Button"]').first
                    if sidebar_post_btn.count() > 0 and sidebar_post_btn.is_visible():
                        sidebar_post_btn.click()
                        time.sleep(2)
                except Exception:
                    pass

                # Locate post input area
                editor = page.locator('div[aria-label="Post text"], div[role="textbox"], div[contenteditable="true"], div[data-contents="true"]').first
                editor.wait_for(state="visible", timeout=25000)
                editor.click()
                editor.fill(text)
                time.sleep(2)

                # Attach image if available
                if image_path and os.path.exists(image_path):
                    try:
                        file_input = page.locator('input[type="file"][accept*="image"]').first
                        if file_input.count() > 0:
                            file_input.set_input_files(image_path)
                            time.sleep(3)
                    except Exception as ie:
                        print(f"[!] Image attach note: {ie}")

                # Click Post button
                post_button = page.locator('button[data-testid="tweetButton"], button[data-testid="tweetButtonInline"]').first
                post_button.wait_for(state="visible", timeout=15000)
                post_button.click()

                time.sleep(6) # Wait for network send
                context.close()

                MemoryDB.log_event("SUCCESS", "XBrowserPoster", f"Posted tweet automatically via Playwright persistent browser!")
                return {"status": "success", "message": "Tweet posted live via Playwright Auto-Poster"}

        except Exception as e:
            err_msg = f"Playwright posting error: {str(e)}"
            MemoryDB.log_event("ERROR", "XBrowserPoster", err_msg)
            return {"status": "failed", "error": str(e)}

if __name__ == "__main__":
    import sys
    poster = XBrowserPoster()
    if len(sys.argv) > 1 and sys.argv[1] == "--login":
        poster.setup_login()
    else:
        print("Run with --login to log in to your X account initially.")
