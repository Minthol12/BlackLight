#!/usr/bin/env python3
"""
BlackLight - AI-Powered OSINT Secret Extractor (Interactive CLI)
Author: Phoenix404/Minthol
License: Educational Use Only

WARNING: Use only on accounts you own or have explicit permission to test.
Unauthorized scraping violates platform ToS and may be illegal.
"""

import argparse
import json
import os
import sys
import time
import random
import re
from datetime import datetime
from typing import List, Dict, Optional, Any

# === Core dependencies ===
try:
    import ollama
except ImportError:
    print("[!] Install ollama: pip install ollama")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[!] Install requests: pip install requests")
    sys.exit(1)

# Optional dependencies for advanced scraping
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("[*] BeautifulSoup4 not installed. Some scraping features may be limited. Install with: pip install beautifulsoup4")

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    INSTALOADER_AVAILABLE = False
    print("[*] Instaloader not installed. Install with: pip install instaloader")


# === Configuration ===
OLLAMA_MODEL_TEXT = "llama3.2:3b"          # For text analysis
OLLAMA_MODEL_VISION = "llama3.2-vision:11b"  # Optional, larger

# ASCII Art Banner
BLACKLIGHT_ASCII = """
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     ██████╗ ██╗      █████╗  ██████╗██╗  ██╗██╗     ██╗ ██████╗ ██╗  ██╗████████╗
║     ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝██║     ██║██╔════╝ ██║  ██║╚══██╔══╝
║     ██████╔╝██║     ███████║██║     █████╔╝ ██║     ██║██║  ███╗███████║   ██║
║     ██╔══██╗██║     ██╔══██║██║     ██╔═██╗ ██║     ██║██║   ██║██╔══██║   ██║
║     ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗███████╗██║╚██████╔╝██║  ██║   ██║
║     ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝
║                                                                      ║
║                    AI-Powered Secret Extractor v2.0                   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# System prompt that defines what a "secret" is
SYSTEM_PROMPT = """
You are BlackLight, an OSINT secret extraction AI. Analyze the following social media post.
Extract any sensitive information that could be used for intelligence gathering or social engineering.
Categories of secrets:
1. LOCATION – addresses, GPS coordinates, landmarks, neighborhood names, workplace, school, gym, favorite cafe, travel plans.
2. IDENTITY – real name (if username is pseudonym), family member names, pet names, birthdate, age, phone fragments, email patterns.
3. ROUTINE – work hours, sleep schedule, days they go to gym, regular commute, recurring appointments.
4. RELATIONSHIP – mentions of friends, partners, coworkers, rivals, secret groups.
5. VULNERABILITY – emotional state (anger, sadness, stress), recent breakup, financial trouble, job dissatisfaction, medical issues.
6. DIGITAL FOOTPRINT – other usernames, linked accounts, devices used, software preferences, security habits.

For each secret found, output JSON exactly like this:
{"secrets": [{"category": "LOCATION", "text": "description", "confidence": 0.95, "evidence": "original snippet"}]}
If no secrets, output {"secrets": []}
Only output JSON, no extra text.
"""


# === Data Models ===
class ContentItem:
    def __init__(self, platform: str, author: str, timestamp: str, text: str, image_path: Optional[str] = None, url: Optional[str] = None):
        self.platform = platform
        self.author = author
        self.timestamp = timestamp
        self.text = text
        self.image_path = image_path
        self.url = url


# === TikTok Scraping Functions ===
def scrape_tiktok_profile(username: str) -> List[Dict]:
    """
    TikTok profile scraping using multiple methods:
    1. Direct JSON extraction from web page
    2. Pyktok if available
    """
    items = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    try:
        # Method 1: Try to use pyktok if available
        try:
            import pyktok as pyk
            pyk.specify_browser('chrome')
            print("[*] Using pyktok for TikTok scraping...")
            # Save metadata to temporary file
            temp_file = f"temp_tiktok_{username}.csv"
            pyk.save_user_video_metadata(username, temp_file)
            if os.path.exists(temp_file):
                # Parse the CSV
                import csv
                with open(temp_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        items.append({
                            "author": username,
                            "timestamp": row.get('create_time', datetime.now().isoformat()),
                            "text": row.get('video_description', ''),
                            "image_url": None,
                            "platform": "tiktok",
                            "url": f"https://tiktok.com/@{username}/video/{row.get('video_id', '')}"
                        })
                os.remove(temp_file)
            return items
        except ImportError:
            print("[*] Pyktok not available. Using fallback method...")
        except Exception as e:
            print(f"[!] Pyktok error: {e}. Using fallback method...")
        
        # Method 2: Direct JSON extraction from web page
        url = f"https://www.tiktok.com/@{username}"
        print(f"[*] Fetching TikTok profile: {url}")
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            # Extract JSON data from script tags
            soup = BeautifulSoup(response.text, 'html.parser') if BS4_AVAILABLE else None
            
            if soup:
                # Look for the JSON data in script tags
                script_tags = soup.find_all('script')
                for script in script_tags:
                    if script.string and '"UserModule"' in script.string:
                        # Extract user info JSON
                        import re
                        json_pattern = r'<script[^>]*>window\.__SIGI_STATE__\s*=\s*({.*?});</script>'
                        match = re.search(json_pattern, str(script))
                        if match:
                            try:
                                data = json.loads(match.group(1))
                                # Parse user data structure
                                if 'UserModule' in data and 'users' in data['UserModule']:
                                    user_data = list(data['UserModule']['users'].values())[0]
                                    # Extract bio/description
                                    bio = user_data.get('bio', {}).get('text', '')
                                    if bio:
                                        items.append({
                                            "author": username,
                                            "timestamp": datetime.now().isoformat(),
                                            "text": f"Bio: {bio}",
                                            "image_url": None,
                                            "platform": "tiktok",
                                            "url": url
                                        })
                                    break
                            except json.JSONDecodeError:
                                continue
            else:
                print("[!] BeautifulSoup not available, skipping HTML parsing")
            
            # Basic text extraction as fallback
            if not items:
                # Try to extract bio with regex
                bio_pattern = r'"bioData":\{"text":"([^"]+)"'
                bio_match = re.search(bio_pattern, response.text)
                if bio_match:
                    items.append({
                        "author": username,
                        "timestamp": datetime.now().isoformat(),
                        "text": f"Bio: {bio_match.group(1)}",
                        "image_url": None,
                        "platform": "tiktok",
                        "url": url
                    })
        
        # Method 3: Try to get recent videos via RSS feed
        rss_url = f"https://www.tiktok.com/@{username}/rss"
        try:
            rss_response = requests.get(rss_url, headers=headers, timeout=10)
            if rss_response.status_code == 200 and BS4_AVAILABLE:
                soup = BeautifulSoup(rss_response.text, 'xml')
                items_rss = soup.find_all('item')
                for item in items_rss[:10]:  # Limit to 10 items
                    title = item.title.text if item.title else ''
                    description = item.description.text if item.description else ''
                    pub_date = item.pubDate.text if item.pubDate else datetime.now().isoformat()
                    combined_text = f"{title} {description}".strip()
                    if combined_text:
                        items.append({
                            "author": username,
                            "timestamp": pub_date,
                            "text": combined_text,
                            "image_url": None,
                            "platform": "tiktok",
                            "url": item.link.text if item.link else None
                        })
        except Exception as rss_error:
            print(f"[!] RSS feed error: {rss_error}")
            
    except Exception as e:
        print(f"[!] TikTok scraping error: {e}")
    return items[:10]  # Limit for performance


# === Snapchat Scraping Functions ===
def scrape_snapchat_profile(username: str) -> List[Dict]:
    """
    Snapchat OSINT gathering using:
    1. SnapIntel library if available
    2. Public profile checks
    3. Bitmoji extraction
    4. Snap Map detection if applicable
    5. Cross-reference with leaked databases (purely illustrative)
    """
    items = []
    headers = {
        'User-Agent': 'Mozilla/5.5 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*'
    }
    
    try:
        # Method 1: Try to use snapintel if available
        try:
            # Check if snapintel is installed
            import subprocess
            result = subprocess.run(['snapintel', '-u', username, '-s'], capture_output=True, text=True, timeout=30)
            if result.stdout:
                items.append({
                    "author": username,
                    "timestamp": datetime.now().isoformat(),
                    "text": f"SnapChat Account Stats:\n{result.stdout[:500]}",
                    "image_url": None,
                    "platform": "snapchat",
                    "url": f"https://www.snapchat.com/add/{username}"
                })
        except (ImportError, subprocess.TimeoutExpired, FileNotFoundError):
            print("[*] SnapIntel not available or timeout. Using fallback methods...")
        
        # Method 2: Basic account existence check through public endpoints
        check_urls = [
            f"https://feelinsonice-hpq.appspot.com/web/deeplink/snapcode?username={username}",
            f"https://www.snapchat.com/add/{username}"
        ]
        
        for url in check_urls:
            try:
                resp = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
                if resp.status_code == 200:
                    items.append({
                        "author": username,
                        "timestamp": datetime.now().isoformat(),
                        "text": f"SnapChat Account exists: {url}",
                        "image_url": None,
                        "platform": "snapchat",
                        "url": url
                    })
                    break
                elif resp.status_code == 302 and "blocked" not in resp.headers.get('Location', ''):
                    items.append({
                        "author": username,
                        "timestamp": datetime.now().isoformat(),
                        "text": f"SnapChat Account exists (redirected): {url}",
                        "image_url": None,
                        "platform": "snapchat",
                        "url": url
                    })
                    break
            except Exception:
                continue
        
        # Method 3: Extract Bitmoji if exists
        bitmoji_url = f"https://app.snapchat.com/web/deeplink/snapcode?username={username}&type=SVG&bitmoji=1"
        try:
            bitmoji_resp = requests.head(bitmoji_url, headers=headers, timeout=10)
            if bitmoji_resp.status_code == 200:
                items.append({
                    "author": username,
                    "timestamp": datetime.now().isoformat(),
                    "text": f"SnapChat Bitmoji found: {bitmoji_url}",
                    "image_url": bitmoji_url,
                    "platform": "snapchat",
                    "url": bitmoji_url
                })
        except Exception:
            pass
        
        # Method 4: Cross-validate with other platforms using username (OSINT correlation)
        if username:
            # Check if username exists on other platforms to confirm activity
            other_platforms = {
                "instagram": f"https://www.instagram.com/{username}/",
                "tiktok": f"https://www.tiktok.com/@{username}",
                "twitter": f"https://twitter.com/{username}",
                "reddit": f"https://www.reddit.com/user/{username}"
            }
            found_platforms = []
            for platform, url in other_platforms.items():
                try:
                    resp = requests.head(url, headers=headers, timeout=5, allow_redirects=False)
                    if resp.status_code == 200:
                        found_platforms.append(platform)
                except Exception:
                    continue
            
            if found_platforms:
                items.append({
                    "author": username,
                    "timestamp": datetime.now().isoformat(),
                    "text": f"Username '{username}' also found active on: {', '.join(found_platforms)}",
                    "image_url": None,
                    "platform": "snapchat",
                    "url": None
                })
        
        # Method 5: If BS4 available, try to extract more data from public profile
        if BS4_AVAILABLE:
            profile_url = f"https://www.snapchat.com/add/{username}"
            try:
                resp = requests.get(profile_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    # Try to find any text content
                    for meta in soup.find_all('meta'):
                        if meta.get('name') == 'description' and meta.get('content'):
                            items.append({
                                "author": username,
                                "timestamp": datetime.now().isoformat(),
                                "text": f"Profile description: {meta['content']}",
                                "image_url": None,
                                "platform": "snapchat",
                                "url": profile_url
                            })
                            break
            except Exception:
                pass
                
    except Exception as e:
        print(f"[!] Snapchat scraping error: {e}")
        
    return items[:10]  # Limit for performance


# === Other Platform Scraping Functions ===
def scrape_instagram(username: str) -> List[Dict]:
    """Scrape Instagram public posts using instaloader."""
    items = []
    if not INSTALOADER_AVAILABLE:
        print("[!] Instaloader not installed. Skipping Instagram.")
        return items
        
    try:
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)
        # Get profile description
        if profile.biography:
            items.append({
                "author": profile.username,
                "timestamp": datetime.now().isoformat(),
                "text": f"Bio: {profile.biography}",
                "image_url": None,
                "platform": "instagram",
                "url": f"https://www.instagram.com/{username}/"
            })
        # Get recent posts
        for post in profile.get_posts():
            items.append({
                "author": profile.username,
                "timestamp": post.date_utc.isoformat(),
                "text": post.caption if post.caption else "",
                "image_url": post.url,
                "platform": "instagram",
                "url": f"https://www.instagram.com/p/{post.shortcode}/"
            })
            if len(items) >= 10:  # limit for demo
                break
    except Exception as e:
        print(f"[!] Instagram error: {e}")
    return items


def scrape_twitter(username: str) -> List[Dict]:
    """Scrape Twitter using nitter.net (alternative frontend) or direct RSS."""
    items = []
    try:
        # Use nitter.net for public access (no API key)
        url = f"https://nitter.net/{username}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and BS4_AVAILABLE:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract tweets
            tweets = soup.find_all('div', class_='tweet-content')
            for tweet in tweets[:10]:
                items.append({
                    "author": username,
                    "timestamp": datetime.now().isoformat(),
                    "text": tweet.get_text(strip=True),
                    "image_url": None,
                    "platform": "twitter",
                    "url": url
                })
        elif response.status_code == 200:
            # Fallback with regex
            import re
            tweet_pattern = r'<div class="tweet-content[^"]*">(.*?)</div>'
            tweets = re.findall(tweet_pattern, response.text, re.DOTALL)
            for tweet in tweets[:10]:
                clean_text = re.sub(r'<[^>]+>', '', tweet).strip()
                if clean_text:
                    items.append({
                        "author": username,
                        "timestamp": datetime.now().isoformat(),
                        "text": clean_text,
                        "image_url": None,
                        "platform": "twitter",
                        "url": url
                    })
    except Exception as e:
        print(f"[!] Twitter error: {e}")
    return items


def scrape_reddit(username: str) -> List[Dict]:
    """Scrape Reddit user posts via JSON API."""
    items = []
    url = f"https://www.reddit.com/user/{username}/submitted/.json?limit=20"
    headers = {"User-Agent": "BlackLight/1.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for child in data["data"]["children"]:
                post = child["data"]
                items.append({
                    "author": post["author"],
                    "timestamp": datetime.fromtimestamp(post["created_utc"]).isoformat(),
                    "text": post["title"] + "\n" + (post.get("selftext") or ""),
                    "image_url": None,
                    "platform": "reddit",
                    "url": f"https://www.reddit.com{post['permalink']}"
                })
    except Exception as e:
        print(f"[!] Reddit error: {e}")
    return items


def scrape_discord(token: str, channel_id: str, limit: int = 50) -> List[Dict]:
    """Discord self-bot (violates ToS – use only on your own servers)."""
    items = []
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages?limit={limit}"
    headers = {"Authorization": token}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            for msg in resp.json():
                items.append({
                    "author": msg["author"]["username"],
                    "timestamp": msg["timestamp"],
                    "text": msg["content"],
                    "image_url": None,
                    "platform": "discord",
                    "url": f"https://discord.com/channels/@me/{channel_id}/{msg['id']}"
                })
        else:
            print(f"[!] Discord API error: {resp.status_code}")
    except Exception as e:
        print(f"[!] Discord error: {e}")
    return items


# === Normalization ===
def normalize_items(raw_items: List[Dict]) -> List[ContentItem]:
    normalized = []
    for item in raw_items:
        normalized.append(ContentItem(
            platform=item["platform"],
            author=item["author"],
            timestamp=item["timestamp"],
            text=item["text"],
            image_path=None,
            url=item.get("url")
        ))
    return normalized


# === Secret Extraction using Ollama ===
def extract_secrets_from_text(text: str) -> List[Dict]:
    """Call local LLM to extract secrets from a single text post."""
    if not text or len(text.strip()) < 5:
        return []
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL_TEXT,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Post: {text}"}
            ],
            options={"temperature": 0.1}
        )
        raw = response["message"]["content"].strip()
        # Clean markdown
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
        data = json.loads(raw)
        return data.get("secrets", [])
    except Exception as e:
        print(f"[!] LLM error: {e}")
        return []


# === Report ===
def generate_report(all_secrets: List[Dict], items_processed: int, output_file: str):
    """Save secrets to JSON and print a summary."""
    report = {
        "generated": datetime.now().isoformat(),
        "items_processed": items_processed,
        "total_secrets": len(all_secrets),
        "secrets_by_category": {},
        "secrets_list": all_secrets
    }
    for secret in all_secrets:
        cat = secret["category"]
        if cat not in report["secrets_by_category"]:
            report["secrets_by_category"][cat] = []
        report["secrets_by_category"][cat].append(secret)

    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "="*60)
    print(f"BlackLight Report – {report['generated']}")
    print(f"Processed {items_processed} posts → Found {len(all_secrets)} secrets")
    for cat, secrets in report["secrets_by_category"].items():
        print(f"\n[{cat}] ({len(secrets)} items)")
        for s in secrets[:3]:
            print(f"  • {s['text']} (conf: {s.get('confidence', 'N/A')})")
    print(f"\nFull report saved to: {output_file}")
    print("="*60)


# === Interactive CLI ===
def interactive_mode():
    os.system('clear' if os.name == 'posix' else 'cls')
    print(BLACKLIGHT_ASCII)
    print("\n[BlackLight Interactive Mode]\n")
    target = input("Target username: ").strip()
    if not target:
        print("[!] No username provided. Exiting.")
        sys.exit(1)

    print("\nAvailable platforms: instagram, twitter, reddit, tiktok, snapchat, discord")
    platforms_input = input("Platforms (space-separated, e.g., 'instagram twitter tiktok snapchat'): ").strip()
    platforms = platforms_input.split() if platforms_input else []

    discord_token = None
    discord_channel = None
    if "discord" in platforms:
        discord_token = input("Discord user token (optional, leave blank to skip): ").strip()
        if discord_token:
            discord_channel = input("Discord channel ID: ").strip()
        else:
            platforms.remove("discord")
            print("[!] Discord skipped (no token).")

    output_file = input("Output filename (default: blacklight_report.json): ").strip()
    if not output_file:
        output_file = "blacklight_report.json"

    return target, platforms, discord_token, discord_channel, output_file


# === Main ===
def main():
    # If command-line arguments provided, use them; else interactive
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="BlackLight - AI-Powered Secret Extractor")
        parser.add_argument("--target", required=True)
        parser.add_argument("--platforms", nargs="+", default=[])
        parser.add_argument("--discord-token", default="")
        parser.add_argument("--discord-channel", default="")
        parser.add_argument("--output", default="blacklight_report.json")
        parser.add_argument("--no-images", action="store_true")
        args = parser.parse_args()
        target = args.target
        platforms = args.platforms
        discord_token = args.discord_token
        discord_channel = args.discord_channel
        output_file = args.output
    else:
        target, platforms, discord_token, discord_channel, output_file = interactive_mode()

    # Display warning
    print("""
    ╔══════════════════════════════════════════════════════════════════════╗
    ║  BLACKLIGHT – AI-Powered Secret Extractor                            ║
    ║  WARNING: Use only on accounts you own or have explicit             ║
    ║  permission to test. Unauthorized scraping violates ToS             ║
    ║  and may be illegal.                                                ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """)

    raw_items = []
    if "instagram" in platforms:
        raw_items.extend(scrape_instagram(target))
    if "twitter" in platforms:
        raw_items.extend(scrape_twitter(target))
    if "reddit" in platforms:
        raw_items.extend(scrape_reddit(target))
    if "tiktok" in platforms:
        raw_items.extend(scrape_tiktok_profile(target))
    if "snapchat" in platforms:
        raw_items.extend(scrape_snapchat_profile(target))
    if "discord" in platforms and discord_token and discord_channel:
        raw_items.extend(scrape_discord(discord_token, discord_channel))

    if not raw_items:
        print("[!] No content scraped. Exiting.")
        sys.exit(1)

    print(f"[+] Scraped {len(raw_items)} posts/comments")
    items = normalize_items(raw_items)

    all_secrets = []
    for idx, item in enumerate(items):
        print(f"[*] Processing {idx+1}/{len(items)}: {item.platform} - {item.author}")
        secrets = extract_secrets_from_text(item.text)
        all_secrets.extend(secrets)

    generate_report(all_secrets, len(items), output_file)


if __name__ == "__main__":
    main()