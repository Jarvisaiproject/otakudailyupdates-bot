import re
from typing import Dict, Any, List
from database.memory import MemoryDB

class InternalLinker:
    """
    Scans newly generated articles and automatically inserts contextual internal links
    to previously published posts stored in the SQLite memory database.
    """

    def inject_internal_links(self, content: str, current_slug: str) -> Dict[str, Any]:
        recent_posts = MemoryDB.get_recent_posts(limit=30)
        
        # Filter out current post
        candidates = [p for p in recent_posts if p.get("slug") != current_slug and p.get("url")]
        
        if not candidates:
            return {"content": content, "links_added": 0}

        links_added = 0
        modified_content = content

        for post in candidates:
            if links_added >= 3:  # Maximum 3 internal links per article for clean SEO
                break

            kw = post.get("primary_keyword")
            title = post.get("title")
            url = post.get("url")

            if not url:
                continue

            # Look for exact or partial phrase match in the article text (case-insensitive)
            search_phrases = [kw, title[:30]]
            for phrase in search_phrases:
                if not phrase or len(phrase) < 5:
                    continue

                pattern = re.compile(r'\b(' + re.escape(phrase) + r')\b', re.IGNORECASE)
                
                # Verify phrase exists and hasn't already been converted to a link
                if pattern.search(modified_content) and f'href="{url}"' not in modified_content:
                    replacement = f'<a href="{url}" title="{title}">{phrase}</a>'
                    modified_content = pattern.sub(replacement, modified_content, count=1)
                    links_added += 1
                    break

        return {
            "content": modified_content,
            "links_added": links_added
        }
