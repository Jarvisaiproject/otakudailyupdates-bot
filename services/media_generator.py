import io
import os
import re
import urllib.parse
import requests
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, Any, Tuple
from config import config

class MediaGenerator:
    """
    Searches the internet for real topic-relevant anime images, 
    optimizes/compresses them using Pillow to 16:9 WebP format, 
    and generates SEO ALT text.
    """

    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media_output")
        os.makedirs(self.output_dir, exist_ok=True)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def generate_and_optimize_featured_image(self, title: str, slug: str, slot_type: str) -> Dict[str, Any]:
        """
        Searches the internet for a photo matching the blog topic,
        downloads and converts it to a 16:9 WebP featured image.
        """
        alt_text = f"Official photo for {title} - {config.SITE_NAME}"
        image_title = f"{title} Featured Image"
        caption = f"Official topic photo coverage for {title} on {config.SITE_NAME}."

        print(f"[*] Searching the web for real image for topic: '{title}'...")
        image_bytes, source_used = self._search_web_image(title, slot_type)

        if not image_bytes:
            print("[!] Web search failed, generating fallback graphic canvas...")
            image_bytes = self._create_fallback_graphic(title, slot_type)
            source_used = "Fallback Canvas"

        # Compress & Optimize using Pillow to 16:9 WebP (1280x720)
        optimized_filepath, filesize = self._optimize_to_webp(image_bytes, slug)

        return {
            "filepath": optimized_filepath,
            "filename": os.path.basename(optimized_filepath),
            "filesize_bytes": filesize,
            "alt_text": alt_text,
            "image_title": image_title,
            "caption": caption,
            "prompt": f"Web image search for '{title}' via {source_used}"
        }

    def _clean_title_keywords(self, title: str) -> str:
        """Extract core subject from headline for better image search results."""
        cleaned = re.sub(r'(?i)(reveals?|announced?|teaser|trailer|official|release|date|details|season \d+|chapter \d+|episode \d+|revisiting|review|spotlight|analysis|manga|anime|main trailer|cast pair|theme song|staff|first look|key visual)', '', title)
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', cleaned)
        cleaned = ' '.join(cleaned.split())
        return cleaned if len(cleaned) >= 3 else title

    def _search_web_image(self, title: str, slot_type: str) -> Tuple[Optional[bytes], str]:
        """
        Searches Kitsu Anime Database, MyAnimeList (Jikan API), and Bing Images
        for real web photos matching the blog topic.
        """
        keywords = self._clean_title_keywords(title)

        # 1. Try Kitsu Official Anime Database (100% official cover/poster artwork)
        try:
            url = f"https://kitsu.io/api/edge/anime?filter[text]={urllib.parse.quote(keywords)}&page[limit]=1"
            r = requests.get(url, headers=self.headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                if data.get("data"):
                    attr = data["data"][0]["attributes"]
                    cover_url = None
                    if attr.get("coverImage") and attr["coverImage"].get("large"):
                        cover_url = attr["coverImage"]["large"]
                    elif attr.get("posterImage") and attr["posterImage"].get("large"):
                        cover_url = attr["posterImage"]["large"]
                    
                    if cover_url:
                        img_bytes = self._download_image(cover_url)
                        if img_bytes:
                            return img_bytes, f"Kitsu Official Database ({cover_url})"
        except Exception as e:
            print(f"[!] Kitsu image search error: {e}")

        # 2. Try MyAnimeList (Jikan API)
        try:
            url = f"https://api.jikan.moe/v4/anime?q={urllib.parse.quote(keywords)}&limit=1"
            r = requests.get(url, headers=self.headers, timeout=6)
            if r.status_code == 200:
                data = r.json()
                if data.get("data"):
                    mal_img = data["data"][0]["images"]["jpg"]["large_image_url"]
                    img_bytes = self._download_image(mal_img)
                    if img_bytes:
                        return img_bytes, f"MyAnimeList ({mal_img})"
        except Exception as e:
            print(f"[!] Jikan image search error: {e}")

        # 3. Try Bing Image Search for 4K Ultra HD wallpapers & visuals
        try:
            bing_query = f"{keywords} anime 4k wallpaper key visual"
            url = f"https://www.bing.com/images/search?q={urllib.parse.quote(bing_query)}&form=HDRSC2&first=1"
            r = requests.get(url, headers=self.headers, timeout=6)
            if r.status_code == 200:
                murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', r.text)
                for img_url in murls[:8]:
                    if any(domain in img_url.lower() for domain in ['anime', 'manga', 'crunchyroll', 'fandom', 'static', 'media', 'wp-content', 'cdn', 'image', 'wallpaper']):
                        if any(img_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            img_bytes = self._download_image(img_url)
                            if img_bytes:
                                return img_bytes, f"Bing 4K Search ({img_url})"
        except Exception as e:
            print(f"[!] Bing image search error: {e}")

        # 4. Try Pollinations AI 4K as final online fallback
        try:
            encoded_prompt = urllib.parse.quote(f"anime 4k ultra hd wallpaper of {keywords}")
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=3840&height=2160&nologo=true&seed=42"
            res = requests.get(url, timeout=8)
            if res.status_code == 200 and len(res.content) > 5000:
                return res.content, "AI 4K Online Fallback"
        except Exception:
            pass

        return None, "None"


    def _download_image(self, url: str) -> Optional[bytes]:
        try:
            res = requests.get(url, headers=self.headers, timeout=8)
            if res.status_code == 200 and len(res.content) > 10000:
                # Test opening with PIL to verify valid high-res image
                test_img = Image.open(io.BytesIO(res.content))
                w, h = test_img.size
                if w >= 400 and h >= 300:
                    return res.content
        except Exception:
            pass
        return None


    def _create_fallback_graphic(self, title: str, slot_type: str) -> bytes:
        width, height = 3840, 2160
        if slot_type == "episode_review":
            bg_color = (20, 24, 40)
            accent_color = (255, 107, 107)
        elif slot_type == "theory":
            bg_color = (18, 18, 32)
            accent_color = (147, 51, 234)
        else:
            bg_color = (15, 23, 42)
            accent_color = (59, 130, 246)

        img = Image.new("RGB", (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, width, 36], fill=accent_color)
        draw.rectangle([0, height - 36, width, height], fill=accent_color)
        draw.rectangle([180, 180, width - 180, height - 180], outline=accent_color, width=9)

        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        text_snippet = (title[:55] + "...") if len(title) > 55 else title
        draw.text((300, 960), text_snippet, fill=(255, 255, 255), font=font)
        draw.text((300, 1140), f"OTAKU DAILY UPDATES | {slot_type.upper().replace('_', ' ')}", fill=accent_color, font=font)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=95)
        return buffer.getvalue()

    def _optimize_to_webp(self, image_bytes: bytes, slug: str) -> Tuple[str, int]:
        """
        Converts and resizes web image to 4K Ultra HD (3840x2160) WebP with high 92% quality.
        """
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img = img.resize((3840, 2160), Image.Resampling.LANCZOS)
        
        output_filename = f"{slug}-featured-4k.webp"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Save as 4K WebP with 92% high clarity compression
        img.save(output_path, "WEBP", quality=92, method=6)
        filesize = os.path.getsize(output_path)
        
        return output_path, filesize


