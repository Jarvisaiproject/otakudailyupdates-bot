from datetime import datetime
from typing import Dict, Any
from config import config
from database.memory import MemoryDB
from services.anime_news_fetcher import AnimeNewsFetcher
from services.episode_tracker import EpisodeTracker
from services.seo_strategist import SEOStrategist
from services.content_writer import ContentWriter
from services.media_generator import MediaGenerator
from services.internal_linker import InternalLinker
from services.wordpress_publisher import WordPressPublisher
from services.social_publisher import SocialPublisher

class AutonomousAgentController:
    """
    Main orchestration controller that executes an autonomous publishing cycle for any given slot.
    """

    def __init__(self):
        self.news_fetcher = AnimeNewsFetcher()
        self.episode_tracker = EpisodeTracker()
        self.seo_strategist = SEOStrategist()
        self.writer = ContentWriter()
        self.media_gen = MediaGenerator()
        self.internal_linker = InternalLinker()
        self.publisher = WordPressPublisher()
        self.social_publisher = SocialPublisher()

    def run_slot_cycle(self, time_key: str) -> Dict[str, Any]:
        slot_info = config.SLOTS.get(time_key, {"name": f"Slot {time_key}", "type": "news", "subtype": "general"})
        slot_name = slot_info["name"]
        slot_type = slot_info["type"]
        
        MemoryDB.log_event("INFO", slot_name, f"Starting autonomous publication cycle for slot: {slot_name}")

        # Step 1: Research / Topic Selection
        if slot_type == "episode_review":
            topic = self.episode_tracker.get_next_episode_for_review()
        elif slot_type == "theory":
            topic = {
                "title": "Jujutsu Kaisen Season 3 Theory: Sukuna's True Binding Vow & The Secret Culling Game Origin",
                "summary": "Deep dive into manga lore and creator statements regarding Sukuna's origin and ancient Jujutsu history.",
                "source": "Otaku Theory Engine",
                "url": "https://otakudailyupdates.com/theory"
            }
        elif slot_type == "spotlight":
            topic = {
                "title": "Manga Spotlight: Top 5 Underrated Dark Fantasy Series Deserving an Anime Adaptation",
                "summary": "Comprehensive analysis of rising dark fantasy manga with stellar artwork and growing readership.",
                "source": "Manga Spotlight",
                "url": "https://otakudailyupdates.com/spotlight"
            }
        else: # News Slots 1 to 5
            topic = self.news_fetcher.get_unseen_trending_topic(subtype=slot_info.get("subtype", "news"))

        title = topic["title"]

        # Step 2: Live WordPress Site Duplicate Check
        if self.publisher.is_published_on_wp(title):
            MemoryDB.log_event("WARNING", slot_name, f"Topic '{title[:40]}...' is already published on live WordPress site. Aborting to prevent duplicate.")
            return {
                "status": "skipped",
                "reason": "duplicate_on_wp",
                "message": f"Topic '{title}' is already published on site."
            }


        # Step 3: SEO Strategy
        seo_meta = self.seo_strategist.analyze_and_plan(title, slot_type, topic.get("summary", ""))

        # Secondary Local Memory Check
        if MemoryDB.is_title_or_slug_duplicate(title, seo_meta["slug"]):
            MemoryDB.log_event("WARNING", slot_name, f"Topic '{title[:40]}...' exists in SQLite memory. Aborting.")
            return {
                "status": "skipped",
                "reason": "duplicate_in_memory",
                "message": f"Topic '{title}' exists in SQLite memory."
            }


        # Step 3: Write Article Content
        written = self.writer.generate_article(topic, seo_meta, slot_info)

        # Step 4: Internal Link Injection
        linked = self.internal_linker.inject_internal_links(written["content"], seo_meta["slug"])
        final_content = linked["content"]
        links_added = linked["links_added"]

        # Step 5: Featured Image Generation & Pillow WebP Compression
        media_meta = self.media_gen.generate_and_optimize_featured_image(title, seo_meta["slug"], slot_type)

        # Step 6: WordPress REST API Publishing with Retries
        article_payload = {
            "content": final_content,
            "word_count": written["word_count"],
            "readability_score": written["readability_score"]
        }
        
        pub_result = self.publisher.publish_post_with_retry(article_payload, seo_meta, media_meta, slot_name)

        if pub_result["success"]:
            # Step 7: Record to SQLite Memory DB
            post_db_id = MemoryDB.save_published_post({
                "title": seo_meta["seo_title"],
                "slug": seo_meta["slug"],
                "slot_name": slot_name,
                "primary_keyword": seo_meta["primary_keyword"],
                "secondary_keywords": seo_meta["secondary_keywords"],
                "category": seo_meta["category"],
                "tags": seo_meta["tags"],
                "url": pub_result["url"],
                "wp_post_id": pub_result["wp_post_id"],
                "word_count": written["word_count"],
                "seo_score": 95 if written["qa_passed"] else 80,
                "readability_score": written["readability_score"],
                "image_prompt": media_meta["prompt"],
                "internal_links_count": links_added
            })

            # If episode review slot, record completed episode in episode tracker DB
            if slot_type == "episode_review" and not topic.get("is_fallback"):
                self.episode_tracker.record_completed_review(
                    anime_name=topic["anime_name"],
                    season=topic["season_number"],
                    episode=topic["episode_number"],
                    review_url=pub_result["url"],
                    rating=9.2
                )

            # Step 8: Social Media Auto-Poster (X / Twitter & Draft Memory)
            social_result = self.social_publisher.publish_to_x(
                article_title=title,
                article_url=pub_result["url"],
                summary=topic.get("summary", title),
                image_path=media_meta.get("filepath"),
                wp_post_id=pub_result.get("wp_post_id")
            )

            MemoryDB.log_event("SUCCESS", slot_name, f"Completed cycle for '{title}'. URL: {pub_result['url']} | X Status: {social_result.get('status')}")

            return {
                "status": "success",
                "post_db_id": post_db_id,
                "title": title,
                "url": pub_result["url"],
                "word_count": written["word_count"],
                "readability": written["readability_score"],
                "links_added": links_added,
                "x_status": social_result.get("status"),
                "dry_run": pub_result.get("dry_run", False)
            }
        else:
            MemoryDB.log_event("ERROR", slot_name, f"Autonomous publication failed after {pub_result.get('attempts')} attempts: {pub_result.get('error')}")
            return {
                "status": "failed",
                "error": pub_result.get("error")
            }
