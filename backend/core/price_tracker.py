"""J.A.R.V.I.S. Autonomous Web Price & Deal Tracker
Monitors product links from Amazon, Flipkart, and eCommerce sites,
records price fluctuations to SQLite, and alerts Sir via proactive HUD events when prices drop.
"""
import re
import urllib.request
from datetime import datetime
from pathlib import Path

from core.database import get_connection

def init_price_tracker_table():
    """Ensure tracked_products table exists in SQLite database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tracked_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE NOT NULL,
        title TEXT,
        target_price REAL,
        current_price REAL,
        lowest_price REAL,
        currency TEXT DEFAULT 'INR',
        last_checked TEXT,
        status TEXT DEFAULT 'active'
    )
    """)
    conn.commit()
    conn.close()

def extract_price_from_html(html: str) -> tuple[float | None, str | None, str]:
    """Parse price and title from Amazon/Flipkart/general HTML via heuristic regex."""
    title = ""
    # Extract Title
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = title_match.group(1).replace("Amazon.in:", "").replace("Flipkart.com:", "").strip()
        title = re.sub(r"\s+", " ", title)[:100]

    # Amazon Price Selectors
    amazon_price = re.search(r'class="a-price-whole"[^>]*>([0-9,]+)', html)
    if amazon_price:
        num = float(amazon_price.group(1).replace(",", ""))
        return num, title, "INR"

    # Flipkart Price Selectors
    flipkart_price = re.search(r'class="Nx9bqj[^"]*"[^>]*>₹([0-9,]+)', html)
    if flipkart_price:
        num = float(flipkart_price.group(1).replace(",", ""))
        return num, title, "INR"

    # Generic Currency Regex (₹ / $ / Rs.)
    generic_inr = re.search(r"(?:₹|Rs\.?)\s*([0-9,]{2,10})", html)
    if generic_inr:
        try:
            num = float(generic_inr.group(1).replace(",", ""))
            return num, title, "INR"
        except Exception:
            pass

    generic_usd = re.search(r"\$\s*([0-9,]{1,8}(?:\.[0-9]{2})?)", html)
    if generic_usd:
        try:
            num = float(generic_usd.group(1).replace(",", ""))
            return num, title, "USD"
        except Exception:
            pass

    return None, title or "Tracked Product", "INR"

def fetch_product_price(url: str) -> dict:
    """Fetch live product webpage and extract current pricing."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")
            price, title, currency = extract_price_from_html(html)
            return {
                "success": price is not None,
                "price": price,
                "title": title,
                "currency": currency,
                "url": url
            }
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}

def add_tracked_product(url: str, target_price: float = None) -> dict:
    """Add a product URL to the autonomous background price watch list."""
    init_price_tracker_table()
    data = fetch_product_price(url)
    curr_price = data.get("price")
    title = data.get("title") or "Tracked Item"
    curr = data.get("currency", "INR")
    now_iso = datetime.now().isoformat()

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO tracked_products (url, title, target_price, current_price, lowest_price, currency, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                target_price = COALESCE(?, target_price),
                current_price = ?,
                lowest_price = MIN(lowest_price, ?),
                last_checked = ?
            """,
            (url, title, target_price, curr_price, curr_price, curr, now_iso, target_price, curr_price, curr_price, now_iso)
        )
        conn.commit()
    finally:
        conn.close()

    price_str = f"{curr} {curr_price:,.2f}" if curr_price else "Price Pending Scan"
    tgt_str = f"Target: {curr} {target_price:,.2f}" if target_price else "No target threshold"
    return {
        "success": True,
        "title": title,
        "current_price": curr_price,
        "currency": curr,
        "message": f"Tracking '{title}': Current: {price_str} ({tgt_str}). Autonomous watch active."
    }

def list_tracked_products() -> list[dict]:
    """List all actively monitored products and their latest pricing."""
    init_price_tracker_table()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, title, target_price, current_price, lowest_price, currency, last_checked FROM tracked_products WHERE status = 'active'")
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "id": r["id"],
            "title": r["title"],
            "url": r["url"],
            "current_price": r["current_price"],
            "target_price": r["target_price"],
            "lowest_price": r["lowest_price"],
            "currency": r["currency"],
            "last_checked": r["last_checked"]
        })
    return results

def check_all_prices() -> list[dict]:
    """Scan all tracked products, update prices, and detect drops."""
    products = list_tracked_products()
    drops = []
    for p in products:
        res = fetch_product_price(p["url"])
        if res.get("success") and res.get("price"):
            new_p = res["price"]
            old_p = p["current_price"]
            tgt_p = p["target_price"]
            
            # If price dropped below previous or target
            if (old_p and new_p < old_p) or (tgt_p and new_p <= tgt_p):
                drops.append({
                    "title": p["title"],
                    "old_price": old_p,
                    "new_price": new_p,
                    "drop_amount": (old_p - new_p) if old_p else 0,
                    "currency": p["currency"],
                    "url": p["url"]
                })
                
            # Update database
            now_iso = datetime.now().isoformat()
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tracked_products
                SET current_price = ?, lowest_price = MIN(lowest_price, ?), last_checked = ?
                WHERE id = ?
                """,
                (new_p, new_p, now_iso, p["id"])
            )
            conn.commit()
            conn.close()
    return drops
