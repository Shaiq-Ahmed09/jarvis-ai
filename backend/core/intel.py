"""Holographic Subject Intel & Media Fetcher for J.A.R.V.I.S.
Fetches high-resolution portraits, media, and images for display in the Stark HUD Optical Viewport.
"""
import json
import re
import urllib.parse
import urllib.request

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

def get_bing_image(query: str) -> str:
    """Fetch high-resolution image URL via Bing Images."""
    try:
        url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}&form=HDRSC2&first=1"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=4) as r:
            html = r.read().decode("utf-8", errors="ignore")
        murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', html)
        if murls:
            for m in murls:
                if any(m.lower().endswith(ext) or ext in m.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    return m
            return murls[0]
        turls = re.findall(r'src=&quot;(https?://tse\d\.mm\.bing\.net/th[^&]+?)&quot;', html)
        if turls:
            return turls[0]
    except Exception as e:
        print(f"Bing image fetch error: {e}")
    return ""

def get_wikipedia_intel(query: str) -> dict:
    """Fetch Wikipedia image and intro summary."""
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={urllib.parse.quote(query)}&prop=pageimages|extracts&exintro=1&explaintext=1&pithumbsize=1000&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisStarkHUD/1.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read())
        pages = data.get("query", {}).get("pages", {})
        for pid, p in pages.items():
            if p.get("thumbnail"):
                return {
                    "title": p.get("title"),
                    "image": p["thumbnail"]["source"],
                    "summary": p.get("extract", "")[:600]
                }
        if pages:
            p = next(iter(pages.values()))
            return {
                "title": p.get("title"),
                "image": "",
                "summary": p.get("extract", "")[:600]
            }
    except Exception as e:
        print(f"Wikipedia intel fetch error: {e}")
    return {"title": query, "image": "", "summary": ""}

def fetch_subject_media(query: str) -> dict:
    """Retrieve optimal image and intel for subject."""
    clean_q = query.strip()
    # Try high-definition web image first
    img_url = get_bing_image(clean_q)
    
    # Also fetch wiki context
    wiki = get_wikipedia_intel(clean_q)
    wiki_img = wiki.get("image", "")
    
    primary_img = img_url or wiki_img
    backup_img = wiki_img if (img_url and wiki_img and img_url != wiki_img) else ""
    
    query_title = clean_q.title()
    wiki_title = wiki.get("title", "")
    if wiki_title and wiki_title.lower() != clean_q.lower() and clean_q.lower() not in wiki_title.lower():
        display_title = f"{query_title} ({wiki_title})"
    else:
        display_title = query_title or wiki_title
        
    return {
        "query": clean_q,
        "title": display_title,
        "image_url": primary_img,
        "backup_url": backup_img,
        "summary": wiki.get("summary", "")
    }
