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
from datetime import datetime
from typing import List, Dict, Optional

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

# === Configuration ===
OLLAMA_MODEL_TEXT = "llama3.2:3b"          # For text analysis
OLLAMA_MODEL_VISION = "llama3.2-vision:11b"  # Optional

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
    def __init__(self, platform: str, author: str, timestamp: str, text: str, image_path: Optional[str] = None):
        self.platform = platform
        self.author = author
        self.timestamp = timestamp
        self.text = text
        self.image_path = image_path


# === Scraping Functions (some are placeholders) ===
def scrape_instagram(username: str) -> List[Dict]:
    """Scrape Instagram public posts using instaloader."""
    items = []
    try:
        import instaloader
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)
        for post in profile.get_posts():
            items.append({
                "author": profile.username,
                "timestamp": post.date_utc.isoformat(),
                "text": post.caption if post.caption else "",
                "image_url": post.url,
                "platform": "instagram"
            })
            if len(items) >= 20:  # limit for demo
                break
    except ImportError:
        print("[!] instaloader not installed. Skipping Instagram.")
    except Exception as e:
        print(f"[!] Instagram error: {e}")
    return items


def scrape_twitter(username: str) -> List[Dict]:
    """Scrape Twitter (X) using snscrape."""
    items = []
    try:
        import snscrape.modules.twitter as sntwitter
        query = f"from:{username}"
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
            items.append({
                "author": tweet.user.username,
                "timestamp": tweet.date.isoformat(),
                "text": tweet.content,
                "image_url": None,
                "platform": "twitter"
            })
            if i >= 20:
                break
    except ImportError:
        print("[!] snscrape not installed. Skipping Twitter.")
    except Exception as e:
        print(f"[!] Twitter error: {e}")
    return items


def scrape_reddit(username: str) -> List[Dict]:
    """Scrape Reddit user posts via JSON API."""
    items = []
    url = f"https://www.reddit.com/user/{username}/submitted/.json?limit=20"
    headers = {"User-Agent": "BlackLight/1.0"}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            for child in data["data"]["children"]:
                post = child["data"]
                items.append({
                    "author": post["author"],
                    "timestamp": datetime.fromtimestamp(post["created_utc"]).isoformat(),
                    "text": post["title"] + "\n" + (post.get("selftext") or ""),
                    "image_url": None,
                    "platform": "reddit"
                })
    except Exception as e:
        print(f"[!] Reddit error: {e}")
    return items


def scrape_tiktok(username: str) -> List[Dict]:
    """Placeholder: TikTok scraping is difficult without API. For demo, return empty."""
    print(f"[*] TikTok scraping not fully implemented. Add your own scraper for @{username}")
    return []


def scrape_snapchat(username: str) -> List[Dict]:
    """Placeholder: Snapchat has no public API. Use only if you have a method."""
    print(f"[*] Snapchat scraping not implemented. Add your own method for @{username}")
    return []


def scrape_discord(token: str, channel_id: str, limit: int = 50) -> List[Dict]:
    """Discord self-bot (violates ToS – use only on your own servers)."""
    items = []
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages?limit={limit}"
    headers = {"Authorization": token}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            for msg in resp.json():
                items.append({
                    "author": msg["author"]["username"],
                    "timestamp": msg["timestamp"],
                    "text": msg["content"],
                    "image_url": None,
                    "platform": "discord"
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
        # For now ignore image download; you can add later
        normalized.append(ContentItem(
            platform=item["platform"],
            author=item["author"],
            timestamp=item["timestamp"],
            text=item["text"],
            image_path=None
        ))
    return normalized


# === Secret Extraction ===
def extract_secrets_from_text(text: str) -> List[Dict]:
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
    print("\n[BlackLight Interactive Mode]")
    target = input("Target username: ").strip()
    if not target:
        print("[!] No username provided. Exiting.")
        sys.exit(1)

    print("\nAvailable platforms: instagram, twitter, reddit, tiktok, snapchat, discord")
    platforms_input = input("Platforms (space-separated, e.g., 'instagram twitter'): ").strip()
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
    ╔══════════════════════════════════════════════════════════════╗
    ║  BLACKLIGHT – AI-Powered Secret Extractor                    ║
    ║  WARNING: Use only on accounts you own or have explicit     ║
    ║  permission to test. Unauthorized scraping violates ToS     ║
    ║  and may be illegal.                                        ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    raw_items = []
    if "instagram" in platforms:
        raw_items.extend(scrape_instagram(target))
    if "twitter" in platforms:
        raw_items.extend(scrape_twitter(target))
    if "reddit" in platforms:
        raw_items.extend(scrape_reddit(target))
    if "tiktok" in platforms:
        raw_items.extend(scrape_tiktok(target))
    if "snapchat" in platforms:
        raw_items.extend(scrape_snapchat(target))
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