import requests
from typing import Dict, Any, Optional, List
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
        Determines the next episode due for review based on SQLite DB tracking memory.
        """
        for series in self.TRACKED_SERIES:
            name = series["name"]
            season = series["season"]
            
            # Check what's the latest reviewed episode in DB
            latest_reviewed = MemoryDB.get_latest_reviewed_episode(name, season)
            next_episode = latest_reviewed + 1
            
            if next_episode <= series["total_episodes"]:
                return {
                    "is_fallback": False,
                    "anime_name": name,
                    "season_number": season,
                    "episode_number": next_episode,
                    "title": f"{name} Season {season} Episode {next_episode} Review",
                    "air_date": datetime.now().strftime("%Y-%m-%d")
                }
                
        # Fallback to Seasonal Review if all episode queues are caught up
        return {
            "is_fallback": True,
            "anime_name": "Best Currently Airing Anime of the Season",
            "season_number": 1,
            "episode_number": 0,
            "title": "Top 10 Must-Watch Currently Airing Anime Series Review & Mid-Season Ranking",
            "air_date": datetime.now().strftime("%Y-%m-%d")
        }

    def record_completed_review(self, anime_name: str, season: int, episode: int, review_url: str, rating: float):
        MemoryDB.update_episode_status(
            anime_name=anime_name,
            season=season,
            episode=episode,
            status="published",
            review_url=review_url,
            rating=rating
        )
