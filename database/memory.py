import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_memory.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA journal_mode = WAL;")
    except Exception:
        pass
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Table for published posts memory
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS published_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            slot_name TEXT,
            primary_keyword TEXT,
            secondary_keywords TEXT,
            category TEXT,
            tags TEXT,
            url TEXT,
            wp_post_id INTEGER,
            published_at TEXT,
            word_count INTEGER,
            seo_score INTEGER,
            readability_score REAL,
            image_prompt TEXT,
            internal_links_count INTEGER DEFAULT 0
        );
        """)
        
        # Table for Episode Tracking System
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS episode_tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            anime_name TEXT NOT NULL,
            season_number INTEGER DEFAULT 1,
            episode_number INTEGER NOT NULL,
            release_date TEXT,
            review_status TEXT DEFAULT 'pending',
            review_url TEXT,
            rating_given REAL,
            updated_at TEXT,
            UNIQUE(anime_name, season_number, episode_number)
        );
        """)
        
        # Table for news sources cache
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_sources_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_hash TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            source_name TEXT,
            source_url TEXT,
            fetched_at TEXT
        );
        """)
        
        # Table for execution logging
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            slot_name TEXT,
            level TEXT,
            message TEXT,
            retry_count INTEGER DEFAULT 0,
            metadata TEXT
        );
        """)
        
        # Table for X (Twitter) & Social media posts memory
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS social_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wp_post_id INTEGER,
            article_title TEXT NOT NULL,
            article_url TEXT NOT NULL,
            x_text TEXT NOT NULL,
            image_path TEXT,
            x_status TEXT DEFAULT 'draft',
            x_tweet_id TEXT,
            created_at TEXT NOT NULL
        );
        """)
        
        conn.commit()

# Initialize DB structure immediately
init_db()

class MemoryDB:
    @staticmethod
    def is_title_or_slug_duplicate(title: str, slug: str) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM published_posts WHERE lower(title) = lower(?) OR lower(slug) = lower(?)", (title.strip(), slug.strip()))
            row = cursor.fetchone()
            return row is not None

    @staticmethod
    def save_published_post(post_data: Dict[str, Any]) -> int:
        slug = post_data.get("slug", "")
        # Append unique timestamp suffix if slug already exists in published_posts
        if MemoryDB.is_title_or_slug_duplicate("", slug):
            slug = f"{slug}-{int(datetime.now().timestamp()) % 10000}"

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO published_posts (
                    title, slug, slot_name, primary_keyword, secondary_keywords, 
                    category, tags, url, wp_post_id, published_at, word_count, 
                    seo_score, readability_score, image_prompt, internal_links_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post_data.get("title"),
                slug,
                post_data.get("slot_name"),
                post_data.get("primary_keyword"),
                json.dumps(post_data.get("secondary_keywords", [])),
                post_data.get("category"),
                json.dumps(post_data.get("tags", [])),
                post_data.get("url"),
                post_data.get("wp_post_id"),
                post_data.get("published_at", datetime.now().isoformat()),
                post_data.get("word_count", 0),
                post_data.get("seo_score", 100),
                post_data.get("readability_score", 70.0),
                post_data.get("image_prompt"),
                post_data.get("internal_links_count", 0)
            ))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_recent_posts(limit: int = 50) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM published_posts ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def update_episode_status(anime_name: str, season: int, episode: int, status: str, review_url: Optional[str] = None, rating: Optional[float] = None):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO episode_tracker (anime_name, season_number, episode_number, release_date, review_status, review_url, rating_given, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(anime_name, season_number, episode_number) DO UPDATE SET
                    review_status=excluded.review_status,
                    review_url=COALESCE(excluded.review_url, episode_tracker.review_url),
                    rating_given=COALESCE(excluded.rating_given, episode_tracker.rating_given),
                    updated_at=excluded.updated_at
            """, (anime_name, season, episode, datetime.now().strftime("%Y-%m-%d"), status, review_url, rating, datetime.now().isoformat()))
            conn.commit()

    @staticmethod
    def get_latest_reviewed_episode(anime_name: str, season: int = 1) -> Optional[int]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(episode_number) as max_ep FROM episode_tracker 
                WHERE anime_name = ? AND season_number = ? AND review_status = 'published'
            """, (anime_name, season))
            row = cursor.fetchone()
            return row["max_ep"] if row and row["max_ep"] is not None else 0

    @staticmethod
    def is_news_processed(news_hash: str) -> bool:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM news_sources_cache WHERE news_hash = ?", (news_hash,))
            row = cursor.fetchone()
            return row is not None

    @staticmethod
    def cache_news(news_hash: str, title: str, source_name: str, source_url: str):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO news_sources_cache (news_hash, title, source_name, source_url, fetched_at)
                VALUES (?, ?, ?, ?, ?)
            """, (news_hash, title, source_name, source_url, datetime.now().isoformat()))
            conn.commit()

    @staticmethod
    def log_event(level: str, slot_name: str, message: str, retry_count: int = 0, metadata: Optional[Dict] = None):
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO agent_logs (timestamp, slot_name, level, message, retry_count, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (datetime.now().isoformat(), slot_name, level, message, retry_count, json.dumps(metadata or {})))
                conn.commit()
        except Exception as e:
            print(f"[LOG ERROR] {e}")

    @staticmethod
    def get_recent_logs(limit: int = 100) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent_logs ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def save_social_post(wp_post_id: Optional[int], article_title: str, article_url: str, x_text: str, image_path: Optional[str] = None, x_status: str = "draft", x_tweet_id: Optional[str] = None) -> int:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO social_posts (wp_post_id, article_title, article_url, x_text, image_path, x_status, x_tweet_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (wp_post_id, article_title, article_url, x_text, image_path, x_status, x_tweet_id, datetime.now().isoformat()))
            conn.commit()
            return cursor.lastrowid

    @staticmethod
    def get_recent_social_posts(limit: int = 50) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM social_posts ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
