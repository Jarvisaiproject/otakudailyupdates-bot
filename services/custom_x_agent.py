import sys
import os
import re
import requests

# Reconfigure stdout/stderr for Windows UTF-8 compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import config
from database.memory import MemoryDB

try:
    import google.genai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    from requests_oauthlib import OAuth1
    HAS_OAUTH = True
except ImportError:
    HAS_OAUTH = False

class CustomXAgent:
    """
    Dedicated Custom AI Social Agent for OtakuDailyUpdates.
    Automatically generates <45 word tweets without hashtags, attaches featured image & URL,
    and posts live to X (@OtakuUpdates106).
    """

    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if self.api_key and HAS_GENAI:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def format_tweet_text(self, title: str, summary: str, url: str) -> str:
        prompt = f"""
You are the dedicated social media AI agent for {config.SITE_NAME}.
Write a high-converting, exciting short tweet for X (Twitter) promoting the following article.

Article Title: {title}
Summary/Context: {summary}

STRICT RULES:
- Maximum length: STRICTLY under 40 words.
- NO HASHTAGS: Absolutely ZERO hashtags (#) are allowed. Do not include any # symbols.
- Style: Punchy, urgent, human, and exciting tone for anime/manga fans.
- Output ONLY the text body. Do not output the URL (the link is added automatically).
"""
        text = ""
        if self.client:
            models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
            for model_name in models_to_try:
                try:
                    res = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    text = res.text or ""
                    if text:
                        break
                except Exception as e:
                    print(f"[CustomXAgent] {model_name} note: {e}")

        if not text:
            text = f"Check out the latest updates on {title}! Read the full story on {config.SITE_NAME}."

        # Strip hashtags and extra spaces
        text = re.sub(r'#\w+', '', text)
        text = re.sub(r'#', '', text).strip()

        words = text.split()
        if len(words) > 40:
            text = " ".join(words[:35]) + "..."

        return f"{text}\n\nRead here: {url}"

    def publish_article_to_x(self, article_title: str, article_url: str, summary: str = "", image_path: Optional[str] = None, wp_post_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Executes full custom agent posting routine to X (@OtakuUpdates106).
        """
        print(f"\n[🤖 Custom X Agent] Processing social post for: '{article_title}'...")

        tweet_text = self.format_tweet_text(article_title, summary or article_title, article_url)

        # Check OAuth 1.0a keys in .env
        api_key = config.TWITTER_API_KEY
        api_secret = config.TWITTER_API_SECRET
        access_token = config.TWITTER_ACCESS_TOKEN
        access_token_secret = config.TWITTER_ACCESS_TOKEN_SECRET

        if not all([api_key, api_secret, access_token, access_token_secret, HAS_OAUTH]):
            print("[🤖 Custom X Agent] Missing Twitter OAuth credentials in .env. Saved as draft.")
            post_id = MemoryDB.save_social_post(wp_post_id, article_title, article_url, tweet_text, image_path, "draft")
            return {"status": "draft", "post_db_id": post_id, "x_text": tweet_text}

        auth = OAuth1(api_key, api_secret, access_token, access_token_secret)

        # Step 1: Upload Image (if present)
        media_id_str = None
        if image_path and os.path.exists(image_path):
            try:
                print("[🤖 Custom X Agent] Uploading featured image to X media endpoint...")
                with open(image_path, "rb") as img_file:
                    res_media = requests.post(
                        "https://upload.twitter.com/1.1/media/upload.json",
                        auth=auth,
                        files={"media": img_file},
                        timeout=30
                    )
                if res_media.status_code in [200, 201]:
                    media_id_str = res_media.json().get("media_id_string")
                    print(f"[🤖 Custom X Agent] Image uploaded successfully (Media ID: {media_id_str})")
            except Exception as me:
                print(f"[🤖 Custom X Agent] Media upload note: {me}")

        # Step 2: Post Tweet via API v2
        try:
            payload = {"text": tweet_text}
            if media_id_str:
                payload["media"] = {"media_ids": [media_id_str]}

            print("[🤖 Custom X Agent] Sending tweet payload to X API v2...")
            res = requests.post(
                "https://api.twitter.com/2/tweets",
                auth=auth,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=25
            )

            if res.status_code in [200, 201]:
                tweet_id = res.json().get("data", {}).get("id")
                print(f"[🤖 Custom X Agent] SUCCESS! Tweet posted live (ID: {tweet_id})")
                post_id = MemoryDB.save_social_post(wp_post_id, article_title, article_url, tweet_text, image_path, "published", tweet_id)
                MemoryDB.log_event("SUCCESS", "CustomXAgent", f"Posted live tweet ID: {tweet_id}")
                return {"status": "success", "tweet_id": tweet_id, "post_db_id": post_id, "x_text": tweet_text}
            else:
                print(f"[🤖 Custom X Agent] X API Status {res.status_code}: {res.text}")
                post_id = MemoryDB.save_social_post(wp_post_id, article_title, article_url, tweet_text, image_path, "draft")
                return {"status": "draft", "error": res.text, "post_db_id": post_id, "x_text": tweet_text}

        except Exception as e:
            print(f"[🤖 Custom X Agent] Execution error: {e}")
            post_id = MemoryDB.save_social_post(wp_post_id, article_title, article_url, tweet_text, image_path, "draft")
            return {"status": "draft", "error": str(e), "post_db_id": post_id, "x_text": tweet_text}

if __name__ == "__main__":
    agent = CustomXAgent()
    res = agent.publish_article_to_x(
        "Demon Slayer Season 5 Release Date & Production Update",
        "https://otakudailyupdates.com/demon-slayer-season-5-infinity-castle-trilogy-production-staff-global-release-guide-8910/"
    )
    print("Agent Result:", res)
