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
    Handles AI featured image generation, Pillow image optimization/compression to 16:9 WebP,
    and ALT text generation.
    """

    def __init__(self):
        self.output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media_output")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_and_optimize_featured_image(self, title: str, slug: str, slot_type: str) -> Dict[str, Any]:
        """
        Generates a 16:9 high quality image, compresses it to WebP, and prepares metadata.
        """
        alt_text = f"Featured illustration for {title} - {config.SITE_NAME}"
        image_title = f"{title} Featured Graphic"
        caption = f"Official featured media coverage for {title} on {config.SITE_NAME}."

        prompt_keywords = re.sub(r'[^a-zA-Z0-9\s]', '', title)
        prompt = f"anime style high quality 16:9 cinematic artwork of {prompt_keywords}, trending on artstation, vivid colors, highly detailed"

        image_bytes = self._fetch_ai_image(prompt)
        
        if not image_bytes:
            # Fallback to local Pillow graphic canvas generation
            image_bytes = self._create_fallback_graphic(title, slot_type)

        # Compress & Optimize using Pillow to 16:9 WebP (1280x720)
        optimized_filepath, filesize = self._optimize_to_webp(image_bytes, slug)

        return {
            "filepath": optimized_filepath,
            "filename": os.path.basename(optimized_filepath),
            "filesize_bytes": filesize,
            "alt_text": alt_text,
            "image_title": image_title,
            "caption": caption,
            "prompt": prompt
        }

    def _fetch_ai_image(self, prompt: str) -> Any:
        try:
            encoded_prompt = urllib.parse.quote(prompt)
            # Pollinations AI image endpoint (free high quality 16:9 generation)
            url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true&seed=42"
            response = requests.get(url, timeout=12)
            if response.status_code == 200 and len(response.content) > 5000:
                return response.content
        except Exception:
            pass
        return None

    def _create_fallback_graphic(self, title: str, slot_type: str) -> bytes:
        width, height = 1280, 720
        # Color palette depending on slot
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

        # Decorative gradients/shapes
        draw.rectangle([0, 0, width, 12], fill=accent_color)
        draw.rectangle([0, height - 12, width, height], fill=accent_color)
        
        # Center badge
        draw.rectangle([60, 60, width - 60, height - 60], outline=accent_color, width=3)

        # Text banner
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        text_snippet = (title[:55] + "...") if len(title) > 55 else title
        draw.text((100, 320), text_snippet, fill=(255, 255, 255), font=font)
        draw.text((100, 380), f"OTAKU DAILY UPDATES | {slot_type.upper().replace('_', ' ')}", fill=accent_color, font=font)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()

    def _optimize_to_webp(self, image_bytes: bytes, slug: str) -> Tuple[str, int]:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        img = img.resize((1280, 720), Image.Resampling.LANCZOS)
        
        output_filename = f"{slug}-featured.webp"
        output_path = os.path.join(self.output_dir, output_filename)
        
        # Save as WebP with 85% compression quality
        img.save(output_path, "WEBP", quality=85, method=6)
        filesize = os.path.getsize(output_path)
        
        return output_path, filesize
