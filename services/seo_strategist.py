import re
import json
from typing import Dict, Any, List
from config import config

class SEOStrategist:
    """
    Generates SEO metadata, slug, keywords, categories, tags, and JSON-LD schema
    customized for OtakuDailyUpdates.
    """

    @staticmethod
    def slugify(text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s-]', '', text)
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'-+', '-', text)
        return text.strip('-')[:100]

    def analyze_and_plan(self, title: str, slot_type: str, topic_summary: str = "") -> Dict[str, Any]:
        slug = self.slugify(title)
        
        # Primary keyword extraction
        words = [w for w in re.findall(r'\w+', title) if len(w) > 3 and w.lower() not in ["with", "from", "that", "this", "have", "will", "official"]]
        primary_keyword = " ".join(words[:4]) if words else title[:40]

        secondary_keywords = [
            f"{primary_keyword} release date",
            f"{primary_keyword} spoilers",
            f"{primary_keyword} news update",
            f"watch {primary_keyword} online",
            f"{primary_keyword} official trailer"
        ]

        # Category determination strictly mapped to user's 3 primary categories: NEWS, REVIEWS, THEORY
        if slot_type in ["news", "spotlight"]:
            category = "NEWS"
            tags = ["Anime News", "Breaking News", "Otaku Updates", "Anime Announcements", primary_keyword]
            schema_type = "NewsArticle"
        elif slot_type == "episode_review":
            category = "REVIEWS"
            tags = ["Episode Review", "Anime Review", "Spoilers", "Season Review", primary_keyword]
            schema_type = "Review"
        elif slot_type == "theory":
            category = "THEORY"
            tags = ["Anime Theory", "Lore Analysis", "Character Theories", "Manga Spoilers", primary_keyword]
            schema_type = "Article"
        else:
            category = "NEWS"
            tags = ["Anime", "Manga", "Japanese Pop Culture", "Otaku Feature", primary_keyword]
            schema_type = "Article"

        meta_title = f"{title} | {config.SITE_NAME}"
        if len(meta_title) > 60:
            meta_title = meta_title[:57] + "..."

        meta_description = f"Read the latest comprehensive coverage of {title}. Full analysis, verified facts, insights, and updates on {config.SITE_NAME}."
        if len(meta_description) > 155:
            meta_description = meta_description[:152] + "..."

        canonical_url = f"{config.WP_URL}/{slug}/"

        # Construct JSON-LD Schema
        json_ld_schema = {
            "@context": "https://schema.org",
            "@type": schema_type,
            "headline": title,
            "description": meta_description,
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": canonical_url
            },
            "author": {
                "@type": "Organization",
                "name": config.SITE_NAME,
                "url": config.WP_URL
            },
            "publisher": {
                "@type": "Organization",
                "name": config.SITE_NAME,
                "logo": {
                    "@type": "ImageObject",
                    "url": f"{config.WP_URL}/logo.png"
                }
            },
            "keywords": ", ".join(tags)
        }

        return {
            "seo_title": title,
            "meta_title": meta_title,
            "meta_description": meta_description,
            "slug": slug,
            "primary_keyword": primary_keyword,
            "secondary_keywords": secondary_keywords,
            "category": category,
            "tags": tags,
            "canonical_url": canonical_url,
            "json_ld_schema": json.dumps(json_ld_schema, indent=2),
            "open_graph": {
                "og:title": meta_title,
                "og:description": meta_description,
                "og:type": "article",
                "og:url": canonical_url
            },
            "twitter_card": {
                "twitter:card": "summary_large_image",
                "twitter:title": meta_title,
                "twitter:description": meta_description
            }
        }
