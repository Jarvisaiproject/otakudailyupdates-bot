import os
import re
import requests
from typing import Dict, Any, Optional
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

class SocialPublisher:
    """
    Automated Social Media Publisher for X (Twitter) & Threads.
    Generates <50 word engaging text with ZERO hashtags, attaches featured image,
    and appends article link. Posts live to Twitter API v2 or saves as draft in SQLite.
    """

    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if self.api_key and HAS_GENAI:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def generate_x_text(self, title: str, summary: str, url: str) -> str:
        prompt = f"""
You are the social media manager for {config.SITE_NAME}.
Write a high-converting, exciting short tweet for X (Twitter) promoting the following article.

Article Title: {title}
Summary/Context: {summary}

CRITICAL RULES:
- Word count: STRICTLY under 45 words.
- NO HASHTAGS: Absolutely ZERO hashtags (#) are allowed. Do not include any # symbols.
- Style: Punchy, urgent, human, and exciting tone for anime/manga fans.
- Output ONLY the text body. Do not output the URL (the system will append the link automatically).
"""
        text = ""
        if self.client:
            models_to_try = ["gemini-flash-latest", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
            for model_name in models_to_try:
                try:
                    res = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    if res and res.text:
                        text = res.text
                        break
                except Exception as e:
                    MemoryDB.log_event("WARNING", "SocialPublisher", f"Gemini model {model_name} failed: {e}. Retrying next model...")


        if not text:
            text = f"Check out the latest updates on {title}! Read the full story on {config.SITE_NAME}."

        # Remove any stray hashtags or markdown
        text = re.sub(r'#\w+', '', text)
        text = re.sub(r'#', '', text)
        text = text.strip()

        # Enforce <45 word limit
        words = text.split()
        if len(words) > 45:
            text = " ".join(words[:40]) + "..."

        # Append URL
        return f"{text}\n\nRead here: {url}"

    def publish_to_x(self, article_title: str, article_url: str, summary: str, image_path: Optional[str] = None, wp_post_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Publishes tweet to X (Twitter) or saves to SQLite memory as draft if API keys are missing.
        """
        if not config.ENABLE_X_POSTING:
            return {"status": "disabled", "message": "X posting is disabled in config"}

        tweet_text = self.generate_x_text(article_title, summary, article_url)

        # Check for X API v2 Credentials
        has_creds = all([
            config.TWITTER_API_KEY,
            config.TWITTER_API_SECRET,
            config.TWITTER_ACCESS_TOKEN,
            config.TWITTER_ACCESS_TOKEN_SECRET,
            HAS_OAUTH
        ])

        if not has_creds or config.DRY_RUN:
            # Save as Draft in DB Memory for $0 cost preview
            post_db_id = MemoryDB.save_social_post(
                wp_post_id=wp_post_id,
                article_title=article_title,
                article_url=article_url,
                x_text=tweet_text,
                image_path=image_path,
                x_status="draft",
                x_tweet_id=None
            )
            MemoryDB.log_event("INFO", "SocialPublisher", f"Saved X Tweet Draft (ID #{post_db_id}): '{article_title[:40]}...'")
            return {
                "status": "draft",
                "post_db_id": post_db_id,
                "x_text": tweet_text,
                "message": "Draft created in SQLite database (Add Twitter API keys to post live)"
            }

        # Live X (Twitter) API v2 Posting
        try:
            auth = OAuth1(
                config.TWITTER_API_KEY,
                config.TWITTER_API_SECRET,
                config.TWITTER_ACCESS_TOKEN,
                config.TWITTER_ACCESS_TOKEN_SECRET
            )

            media_id_str = None
            if image_path and os.path.exists(image_path):
                # Step 1: Upload Media to Twitter API v1.1 endpoint
                with open(image_path, 'rb') as img_file:
                    media_res = requests.post(
                        "https://upload.twitter.com/1.1/media/upload.json",
                        auth=auth,
                        files={"media": img_file},
                        timeout=30
                    )
                if media_res.status_code in [200, 201]:
                    media_id_str = media_res.json().get("media_id_string")

            # Step 2: Post Tweet via Twitter API v2 endpoint
            tweet_payload = {"text": tweet_text}
            if media_id_str:
                tweet_payload["media"] = {"media_ids": [media_id_str]}

            res = requests.post(
                "https://api.twitter.com/2/tweets",
                auth=auth,
                json=tweet_payload,
                headers={"Content-Type": "application/json"},
                timeout=20
            )

            if res.status_code in [200, 201]:
                res_data = res.json()
                tweet_id = res_data.get("data", {}).get("id")

                post_db_id = MemoryDB.save_social_post(
                    wp_post_id=wp_post_id,
                    article_title=article_title,
                    article_url=article_url,
                    x_text=tweet_text,
                    image_path=image_path,
                    x_status="published",
                    x_tweet_id=tweet_id
                )
                MemoryDB.log_event("SUCCESS", "SocialPublisher", f"Published live to X via API (Tweet ID: {tweet_id})")
                return {
                    "status": "success",
                    "tweet_id": tweet_id,
                    "post_db_id": post_db_id,
                    "x_text": tweet_text
                }
            else:
                raise Exception(f"Twitter API v2 returned HTTP {res.status_code}: {res.text}")

        except Exception as e:
            # Fallback to Playwright Browser Poster
            MemoryDB.log_event("INFO", "SocialPublisher", f"API posting fallback: Trying Playwright Browser Auto-Poster...")
            try:
                from services.x_browser_poster import XBrowserPoster
                browser_poster = XBrowserPoster()
                b_res = browser_poster.post_tweet(tweet_text, image_path)
                if b_res.get("status") == "success":
                    post_db_id = MemoryDB.save_social_post(
                        wp_post_id=wp_post_id,
                        article_title=article_title,
                        article_url=article_url,
                        x_text=tweet_text,
                        image_path=image_path,
                        x_status="published",
                        x_tweet_id=None
                    )
                    return {"status": "success", "post_db_id": post_db_id, "x_text": tweet_text}
            except Exception as be:
                MemoryDB.log_event("WARNING", "SocialPublisher", f"Playwright fallback note: {be}")

            # Save as Draft in SQLite DB
            post_db_id = MemoryDB.save_social_post(
                wp_post_id=wp_post_id,
                article_title=article_title,
                article_url=article_url,
                x_text=tweet_text,
                image_path=image_path,
                x_status="draft",
                x_tweet_id=None
            )
            return {
                "status": "draft",
                "error": str(e),
                "post_db_id": post_db_id,
                "x_text": tweet_text
            }
