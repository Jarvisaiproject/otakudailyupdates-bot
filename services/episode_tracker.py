import requests
from typing import Dict, Any, Optional, List
from config import config
from database.memory import MemoryDB
from datetime import datetime


class EpisodeTracker:
    """
    Manages currently airing anime schedule tracking,
    episode sequence progression (Ep 1 -> Ep 2), and ensures zero duplicate reviews.
    """
    
    # Active anime series tracked for the current season
    TRACKED_SERIES = [
        {"name": "Solo Leveling", "season": 2, "total_episodes": 12},
        {"name": "Jujutsu Kaisen", "season": 3, "total_episodes": 24},
        {"name": "Demon Slayer", "season": 5, "total_episodes": 11},
        {"name": "Chainsaw Man", "season": 2, "total_episodes": 12},
        {"name": "Bleach Thousand-Year Blood War", "season": 3, "total_episodes": 13},
        {"name": "Kaiju No. 8", "season": 2, "total_episodes": 12},
        {"name": "Tower of God", "season": 2, "total_episodes": 13},
    ]

    def get_next_episode_for_review(self) -> Dict[str, Any]:
        """
        Determines the next episode due for review based on SQLite DB tracking memory
        AND live WordPress REST API checks to ensure zero duplicate reviews.
        """
        from services.wordpress_publisher import WordPressPublisher
        wp_pub = WordPressPublisher()

        for series in self.TRACKED_SERIES:
            name = series["name"]
            season = series["season"]
            
            # Check latest reviewed episode in DB
            latest_reviewed = MemoryDB.get_latest_reviewed_episode(name, season)
            next_episode = max(1, latest_reviewed + 1)
            
            while next_episode <= series["total_episodes"]:
                ep_title = f"{name} Season {season} Episode {next_episode} Review"
                
                # Check if this exact episode review is already on live WordPress site
                if wp_pub.is_published_on_wp(ep_title):
                    MemoryDB.log_event("INFO", "EpisodeTracker", f"Episode '{ep_title}' already published on WP. Advancing to next episode.")
                    # Record in local DB so next loop knows
                    MemoryDB.update_episode_status(name, season, next_episode, "published", f"{config.WP_URL}/review", 9.0)
                    next_episode += 1
                    continue

                return {
                    "is_fallback": False,
                    "anime_name": name,
                    "season_number": season,
                    "episode_number": next_episode,
                    "title": ep_title,
                    "air_date": datetime.now().strftime("%Y-%m-%d")
                }
                
        # Fallback to Seasonal Review if all episode queues are caught up
        fallback_title = "Top 10 Must-Watch Currently Airing Anime Series Review & Mid-Season Ranking"
        if wp_pub.is_published_on_wp(fallback_title):
            import time
            fallback_title = f"Seasonal Otaku Breakdown: Complete Anime Mid-Season Review #{str(int(time.time()))[-4:]}"

        return {
            "is_fallback": True,
            "anime_name": "Best Currently Airing Anime of the Season",
            "season_number": 1,
            "episode_number": 0,
            "title": fallback_title,
            "air_date": datetime.now().strftime("%Y-%m-%d")
        }


    def get_anime_folders_status(self) -> List[Dict[str, Any]]:
        """
        Returns full folder hierarchy for tracked anime series in <0.5 seconds
        by fetching all live WordPress posts in a single batch request.
        """
        from services.wordpress_publisher import WordPressPublisher
        import urllib.parse
        import html
        import re
        from difflib import SequenceMatcher

        wp_pub = WordPressPublisher()
        
        # 1. Single Batch Fetch of live WP posts
        wp_posts_map = {}
        try:
            res = requests.get(f"{config.WP_URL}/wp-json/wp/v2/posts?per_page=100", headers=wp_pub.headers, timeout=8)
            if res.status_code == 200:
                for p in res.json():
                    t_clean = re.sub(r'[^a-z0-9]', '', html.unescape(p.get("title", {}).get("rendered", "")).lower())
                    wp_posts_map[t_clean] = p.get("link", f"{config.WP_URL}/")
        except Exception as e:
            pass

        folders = []

        for series in self.TRACKED_SERIES:
            name = series["name"]
            season = series["season"]
            total_eps = series["total_episodes"]
            
            ep_records = MemoryDB.get_anime_episodes_list(name, season)
            db_eps_map = {r["episode_number"]: r.get("review_url") for r in ep_records}

            episodes = []
            max_pub = 0
            for ep_num in range(1, total_eps + 1):
                ep_title = f"{name} Season {season} Episode {ep_num} Review"
                norm_target = re.sub(r'[^a-z0-9]', '', ep_title.lower())
                
                # Check DB first or single-batch WP map
                if ep_num in db_eps_map:
                    episodes.append({
                        "episode": ep_num,
                        "title": ep_title,
                        "status": "published",
                        "url": db_eps_map[ep_num] or f"{config.WP_URL}/"
                    })
                    max_pub = max(max_pub, ep_num)
                elif norm_target in wp_posts_map:
                    episodes.append({
                        "episode": ep_num,
                        "title": ep_title,
                        "status": "published",
                        "url": wp_posts_map[norm_target]
                    })
                    max_pub = max(max_pub, ep_num)

            folders.append({
                "anime_name": name,
                "season": season,
                "total_episodes": total_eps,
                "published_count": len(episodes),
                "latest_episode": max_pub,
                "next_due_episode": max_pub + 1 if max_pub < total_eps else None,
                "episodes": episodes,
                "is_active": max_pub < total_eps
            })

        return folders


    def record_completed_review(self, anime_name: str, season: int, episode: int, review_url: str, rating: float):
        MemoryDB.update_episode_status(
            anime_name=anime_name,
            season=season,
            episode=episode,
            status="published",
            review_url=review_url,
            rating=rating
        )

