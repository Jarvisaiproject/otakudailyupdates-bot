import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    WP_URL = os.getenv("WP_URL", "https://otakudailyupdates.com").rstrip("/")
    WP_USERNAME = os.getenv("WP_USER", os.getenv("WP_USERNAME", "otakuwears664@gmail.com"))
    WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
    
    # Twitter / X API Credentials
    ENABLE_X_POSTING = os.getenv("ENABLE_X_POSTING", "true").lower() == "true"
    TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_CLIENT_ID = os.getenv("TWITTER_CLIENT_ID", "")
    TWITTER_CLIENT_SECRET = os.getenv("TWITTER_CLIENT_SECRET", "")
    TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")
    TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")
    
    SITE_NAME = os.getenv("SITE_NAME", "Otaku Daily Updates")
    NICHE = os.getenv("NICHE", "Anime, Manga, Movies, Light Novels, Games, Japanese Pop Culture")
    
    # 15 Daily Automated Slots (10 News, 3 Episode Reviews, 1 Theory, 1 Spotlight)
    SLOTS = {
        "01:00": {"name": "Anime News #1", "type": "news", "subtype": "breaking"},
        "03:00": {"name": "Anime News #2", "type": "news", "subtype": "trending"},
        "05:00": {"name": "Anime News #3", "type": "news", "subtype": "release_dates"},
        "07:00": {"name": "Episode Review #1", "type": "episode_review", "subtype": "airing_review"},
        "08:30": {"name": "Anime News #4", "type": "news", "subtype": "announcements"},
        "10:00": {"name": "Anime Theory", "type": "theory", "subtype": "lore_analysis"},
        "11:30": {"name": "Anime News #5", "type": "news", "subtype": "voice_cast_staff"},
        "13:00": {"name": "Episode Review #2", "type": "episode_review", "subtype": "airing_review"},
        "14:30": {"name": "Anime News #6", "type": "news", "subtype": "studio_production"},
        "16:00": {"name": "Otaku Spotlight", "type": "spotlight", "subtype": "manga_novel_games"},
        "17:30": {"name": "Anime News #7", "type": "news", "subtype": "trailers_visuals"},
        "19:00": {"name": "Episode Review #3", "type": "episode_review", "subtype": "airing_review"},
        "20:30": {"name": "Anime News #8", "type": "news", "subtype": "box_office_ranking"},
        "22:00": {"name": "Anime News #9", "type": "news", "subtype": "licensing_manga"},
        "23:30": {"name": "Anime News #10", "type": "news", "subtype": "late_night_roundup"},
    }

    
    # Trusted RSS Sources for Anime News Aggregation
    TRUSTED_RSS_SOURCES = [
        {"name": "Crunchyroll News", "url": "https://www.crunchyroll.com/news/rss"},
        {"name": "Anime News Network", "url": "https://www.animenewsnetwork.com/all/rss.xml"},
        {"name": "MyAnimeList News", "url": "https://myanimelist.net/rss/news.xml"},
        {"name": "Reddit Anime News", "url": "https://www.reddit.com/r/anime/hot.rss"},
    ]
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_SECONDS = 300  # 5 minutes
    
    # Target word counts
    MIN_WORD_COUNT = 1500
    MAX_WORD_COUNT = 2500

config = Config()
