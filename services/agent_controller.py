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

    def run_slot_cycle(self, time_key: str = "auto") -> Dict[str, Any]:
        if time_key in ["auto", "", None] or time_key not in config.SLOTS:
            now_str = datetime.now().strftime("%H:%M")
            # Find closest slot by time
            time_keys = list(config.SLOTS.keys())
            time_key = min(time_keys, key=lambda k: abs((datetime.strptime(k, "%H:%M") - datetime.strptime(now_str, "%H:%M")).total_seconds()))

        slot_info = config.SLOTS.get(time_key, {"name": f"Slot {time_key}", "type": "news", "subtype": "general"})
        slot_name = slot_info["name"]
        slot_type = slot_info["type"]
        
        MemoryDB.log_event("INFO", slot_name, f"Starting autonomous publication cycle for slot: {slot_name}")

        # Step 1: Research / Topic Selection
        if slot_type == "episode_review":
            topic = self.episode_tracker.get_next_episode_for_review()
        elif slot_type == "theory":
            import random
            theories = [
                {"title": "Jujutsu Kaisen Season 3 Theory: Sukuna's True Binding Vow & The Secret Culling Game Origin", "summary": "Deep dive into manga lore and creator statements regarding Sukuna's origin and ancient Jujutsu history."},
                {"title": "Solo Leveling Season 2 Theory: Sung Jin-Woo's Monarch Power Origin & The Secret Shadow Realm", "summary": "Comprehensive analysis of Shadow Monarch lore and upcoming Monarch battles in Season 2."},
                {"title": "One Piece Elbaf Theory: Shank's Secret Family Lineage & The True Purpose of the Sun God Nika", "summary": "Lore analysis on Shank's connection to Figarland family and Elbaf's ancient prophecy."},
                {"title": "Demon Slayer Theory: Yoriichi's Sun Breathing Origin & The Secret Weakness of Muzan Kibutsuji", "summary": "Detailed breakdown of Sun Breathing lineage and Muzan's cellular fear of Yoriichi."},
                {"title": "Chainsaw Man Season 2 Theory: The Reze Arc Secret & The Four Horsemen Devil Hierarchy", "summary": "In-depth breakdown of Bomb Devil lore and Makima's ultimate horsemen endgame."}
            ]
            chosen = random.choice(theories)
            # Ensure not already published on WP
            for th in theories:
                if not self.publisher.is_published_on_wp(th["title"]):
                    chosen = th
                    break
            topic = {
                "title": chosen["title"],
                "summary": chosen["summary"],
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
        else: # News Slots
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

        # Step 4: Internal Link Injection & Episode Navigation Widget
        linked = self.internal_linker.inject_internal_links(written["content"], seo_meta["slug"])
        final_content = linked["content"]
        links_added = linked["links_added"]

        if slot_type == "episode_review" and not topic.get("is_fallback"):
            nav_widget = self.episode_tracker.generate_episode_nav_widget(
                anime_name=topic.get("anime_name", "Anime"),
                season=topic.get("season_number", 1),
                current_ep=topic.get("episode_number", 1),
                total_eps=12
            )
            final_content += "\n\n" + nav_widget

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
