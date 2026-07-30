import sys
import os
import base64
import html
import requests
from difflib import SequenceMatcher
from typing import Dict, Any

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import config
from database.memory import MemoryDB



class WPDuplicateCleanerAgent:
    """
    Autonomous WordPress Duplicate Cleaner Agent.
    Scans live WordPress posts periodically, identifies duplicates (>60% similarity),
    and permanently deletes duplicate posts from WordPress.
    """

    def __init__(self):
        self.wp_url = config.WP_URL
        self.username = config.WP_USERNAME
        self.app_password = config.WP_APP_PASSWORD
        
        auth_string = f"{self.username}:{self.app_password}"
        token = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        self.headers = {
            "Authorization": f"Basic {token}"
        }

    def scan_and_clean_duplicates(self) -> Dict[str, Any]:
        """
        Scans published posts on WordPress REST API.
        If duplicates (>60% similarity match) are found:
        Keeps the original post and permanently deletes duplicate posts.
        """
        MemoryDB.log_event("INFO", "WPCleanerAgent", "Starting autonomous WordPress duplicate scan...")
        try:
            res = requests.get(f"{self.wp_url}/wp-json/wp/v2/posts?per_page=100&status=publish", headers=self.headers, timeout=15)
            if res.status_code != 200:
                raise Exception(f"WP API returned HTTP {res.status_code}: {res.text}")

            posts = res.json()
            if not posts:
                MemoryDB.log_event("INFO", "WPCleanerAgent", "No published posts found on site.")
                return {"scanned": 0, "deleted": 0, "deleted_details": []}

            processed_ids = set()
            deleted_posts = []

            for i in range(len(posts)):
                p1 = posts[i]
                id1 = p1.get("id")
                if id1 in processed_ids:
                    continue

                title1 = html.unescape(p1.get("title", {}).get("rendered", "")).strip()

                for j in range(i + 1, len(posts)):
                    p2 = posts[j]
                    id2 = p2.get("id")
                    if id2 in processed_ids:
                        continue

                    title2 = html.unescape(p2.get("title", {}).get("rendered", "")).strip()

                    ratio = SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
                    if ratio > 0.60:
                        # Found duplicate! Keep original (lower ID) and delete duplicate (higher ID)
                        keep_post = p1 if id1 < id2 else p2
                        del_post = p2 if id1 < id2 else p1
                        del_id = del_post.get("id")
                        del_title = html.unescape(del_post.get("title", {}).get("rendered", ""))

                        del_res = requests.delete(
                            f"{self.wp_url}/wp-json/wp/v2/posts/{del_id}?force=true",
                            headers=self.headers,
                            timeout=15
                        )

                        if del_res.status_code in [200, 204]:
                            processed_ids.add(del_id)
                            deleted_posts.append({
                                "id": del_id,
                                "title": del_title,
                                "kept_id": keep_post.get("id")
                            })
                            MemoryDB.log_event("SUCCESS", "WPCleanerAgent", f"Deleted duplicate post ID #{del_id}: '{del_title[:40]}...' (Kept original ID #{keep_post.get('id')})")

            MemoryDB.log_event("INFO", "WPCleanerAgent", f"Scan complete. Scanned {len(posts)} posts. Deleted {len(deleted_posts)} duplicates.")
            return {
                "scanned": len(posts),
                "deleted": len(deleted_posts),
                "deleted_details": deleted_posts
            }

        except Exception as e:
            err_msg = f"WP Cleaner Agent error: {e}"
            MemoryDB.log_event("ERROR", "WPCleanerAgent", err_msg)
            return {"status": "error", "message": err_msg}

if __name__ == "__main__":
    agent = WPDuplicateCleanerAgent()
    print("Cleaner Agent Test:", agent.scan_and_clean_duplicates())
