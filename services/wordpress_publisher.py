import time
import requests
import base64
from typing import Dict, Any, Optional, List
from config import config
from database.memory import MemoryDB

class WordPressPublisher:
    """
    Handles WordPress REST API authentication, media uploads, taxonomy resolution,
    and post publishing with automatic 3x retries and Yoast/RankMath meta support.
    """

    def __init__(self):
        self.wp_url = config.WP_URL
        self.username = config.WP_USERNAME
        self.app_password = config.WP_APP_PASSWORD
        self.dry_run = config.DRY_RUN

        # Basic Auth Header
        auth_string = f"{self.username}:{self.app_password}"
        token = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        self.headers = {
            "Authorization": f"Basic {token}"
        }

    def publish_post_with_retry(self, article: Dict[str, Any], seo_meta: Dict[str, Any], media_meta: Dict[str, Any], slot_name: str) -> Dict[str, Any]:
        """
        Executes publication with automatic retries up to MAX_RETRIES with 5-minute backoff.
        """
        for attempt in range(1, config.MAX_RETRIES + 1):
            try:
                if self.dry_run:
                    # Dry Run Simulation
                    simulated_wp_id = 99900 + int(time.time()) % 1000
                    simulated_url = f"{self.wp_url}/{seo_meta['slug']}/"
                    
                    MemoryDB.log_event("SUCCESS", slot_name, f"[DRY-RUN] Published post '{seo_meta['seo_title']}' (ID: {simulated_wp_id})", retry_count=attempt-1)
                    
                    return {
                        "success": True,
                        "wp_post_id": simulated_wp_id,
                        "url": simulated_url,
                        "dry_run": True,
                        "attempts": attempt
                    }

                # Live WordPress API Publishing Pipeline
                # Step 1: Upload Media
                media_id = self._upload_media(media_meta)
                
                # Step 2: Resolve Category & Tags
                category_id = self._get_or_create_category(seo_meta.get("category", "Uncategorized"))
                tag_ids = self._get_or_create_tags(seo_meta.get("tags", []))

                # Step 3: Create Post Payload
                post_payload = {
                    "title": seo_meta["seo_title"],
                    "slug": seo_meta["slug"],
                    "content": article["content"],
                    "excerpt": seo_meta["meta_description"],
                    "status": "publish",
                    "categories": [category_id] if category_id else [],
                    "tags": tag_ids,
                    "meta": {
                        "_yoast_wpseo_title": seo_meta["meta_title"],
                        "_yoast_wpseo_metadesc": seo_meta["meta_description"],
                        "rank_math_title": seo_meta["meta_title"],
                        "rank_math_description": seo_meta["meta_description"]
                    }
                }
                
                if media_id:
                    post_payload["featured_media"] = media_id

                # Post Request to WP REST API
                res = requests.post(
                    f"{self.wp_url}/wp-json/wp/v2/posts",
                    json=post_payload,
                    headers=self.headers,
                    timeout=20
                )
                
                if res.status_code in [200, 201]:
                    post_res = res.json()
                    wp_post_id = post_res.get("id")
                    url = post_res.get("link", f"{self.wp_url}/{seo_meta['slug']}/")

                    MemoryDB.log_event("SUCCESS", slot_name, f"Successfully published to WP: '{seo_meta['seo_title']}' (ID: {wp_post_id})", retry_count=attempt-1)

                    return {
                        "success": True,
                        "wp_post_id": wp_post_id,
                        "url": url,
                        "dry_run": False,
                        "attempts": attempt
                    }
                else:
                    raise Exception(f"WP REST API returned status code {res.status_code}: {res.text}")

            except Exception as e:
                err_msg = f"Publish attempt #{attempt} failed for '{seo_meta.get('seo_title')}': {str(e)}"
                MemoryDB.log_event("WARNING" if attempt < config.MAX_RETRIES else "ERROR", slot_name, err_msg, retry_count=attempt)
                
                if attempt < config.MAX_RETRIES:
                    time.sleep(config.RETRY_DELAY_SECONDS)
                else:
                    return {
                        "success": False,
                        "error": str(e),
                        "attempts": attempt
                    }

    def _upload_media(self, media_meta: Dict[str, Any]) -> Optional[int]:
        try:
            filepath = media_meta["filepath"]
            filename = media_meta["filename"]
            
            with open(filepath, "rb") as f:
                media_bytes = f.read()

            upload_headers = self.headers.copy()
            upload_headers["Content-Type"] = "image/webp"
            upload_headers["Content-Disposition"] = f'attachment; filename="{filename}"'

            res = requests.post(
                f"{self.wp_url}/wp-json/wp/v2/media",
                data=media_bytes,
                headers=upload_headers,
                timeout=20
            )

            if res.status_code in [200, 201]:
                media_res = res.json()
                media_id = media_res.get("id")
                
                # Update alt text and title
                requests.post(
                    f"{self.wp_url}/wp-json/wp/v2/media/{media_id}",
                    json={
                        "alt_text": media_meta.get("alt_text", ""),
                        "title": media_meta.get("image_title", ""),
                        "caption": media_meta.get("caption", "")
                    },
                    headers=self.headers,
                    timeout=10
                )
                return media_id
        except Exception as e:
            MemoryDB.log_event("WARNING", "WP Media", f"Media upload failed: {str(e)}")
        return None

    def _get_or_create_category(self, cat_name: str) -> Optional[int]:
        try:
            res = requests.get(f"{self.wp_url}/wp-json/wp/v2/categories?per_page=100", headers=self.headers, timeout=10)
            if res.status_code == 200:
                cats = res.json()
                # Exact name match (case-insensitive)
                for c in cats:
                    if c["name"].strip().upper() == cat_name.strip().upper():
                        return c["id"]
                # Partial/Slug match
                for c in cats:
                    if cat_name.lower() in c["name"].lower() or cat_name.lower() in c["slug"].lower():
                        return c["id"]
            
            # Create new category if not found
            create_res = requests.post(f"{self.wp_url}/wp-json/wp/v2/categories", json={"name": cat_name.upper()}, headers=self.headers, timeout=10)
            if create_res.status_code in [200, 201]:
                return create_res.json()["id"]
        except Exception:
            pass
        return None

    def _get_or_create_tags(self, tags: List[str]) -> List[int]:
        tag_ids = []
        for tag in tags[:5]:
            try:
                res = requests.get(f"{self.wp_url}/wp-json/wp/v2/tags?search={tag}", headers=self.headers, timeout=10)
                if res.status_code == 200:
                    found = res.json()
                    if found:
                        tag_ids.append(found[0]["id"])
                        continue
                
                create_res = requests.post(f"{self.wp_url}/wp-json/wp/v2/tags", json={"name": tag}, headers=self.headers, timeout=10)
                if create_res.status_code in [200, 201]:
                    tag_ids.append(create_res.json()["id"])
            except Exception:
                pass
        return tag_ids

    def is_published_on_wp(self, title: str) -> bool:
        """
        Queries WordPress REST API to check if a post with the EXACT SAME title or topic is already published.
        Uses normalized title matching (strips spaces, punctuation, special chars) with strict 85%+ threshold.
        """
        try:
            import urllib.parse
            import html
            import re
            from difflib import SequenceMatcher

            clean_title = title.strip().lower()
            norm_target = re.sub(r'[^a-z0-9]', '', clean_title)
            search_query = urllib.parse.quote(clean_title[:30])

            res = requests.get(f"{self.wp_url}/wp-json/wp/v2/posts?search={search_query}&per_page=15", headers=self.headers, timeout=8)
            if res.status_code == 200:
                posts = res.json()
                for p in posts:
                    wp_raw = html.unescape(p.get("title", {}).get("rendered", "")).strip().lower()
                    norm_wp = re.sub(r'[^a-z0-9]', '', wp_raw)

                    # Strict title match: Exact normalized title match or > 85% similarity
                    ratio = SequenceMatcher(None, norm_target, norm_wp).ratio()
                    if norm_target == norm_wp or ratio > 0.85:
                        return True

            res2 = requests.get(f"{self.wp_url}/wp-json/wp/v2/posts?per_page=25", headers=self.headers, timeout=8)
            if res2.status_code == 200:
                posts2 = res2.json()
                for p in posts2:
                    wp_raw = html.unescape(p.get("title", {}).get("rendered", "")).strip().lower()
                    norm_wp = re.sub(r'[^a-z0-9]', '', wp_raw)
                    ratio = SequenceMatcher(None, norm_target, norm_wp).ratio()
                    if norm_target == norm_wp or ratio > 0.85:
                        return True

        except Exception as e:
            MemoryDB.log_event("WARNING", "WP Duplicate Check", f"Failed WP live check: {e}")
        return False



