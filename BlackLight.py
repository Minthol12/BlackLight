#!/usr/bin/env python3
"""
BlackLight - AI-Powered OSINT Secret Extractor
Author: Your Name / College Project
License: Educational Use Only

WARNING: Use only on accounts you own or have explicit permission to test.
Unauthorized scraping violates platform ToS and may be illegal.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional

# === Core dependencies (install with pip) ===
# pip install ollama requests pillow
# Optional for Instagram: pip install instaloader
# Optional for Discord: create a bot or use user token

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
OLLAMA_MODEL_TEXT = "llama3.2:3b"      # For text analysis
OLLAMA_MODEL_VISION = "llama3.2-vision:11b"  # Optional, larger

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
    def __init__(self, platform: str, author: str, timestamp: str, text: str, image_path: Optional[str] = None):
        self.platform = platform
        self.author = author
        self.timestamp = timestamp
        self.text = text
        self.image_path = image_path

    def to_dict(self):
        return {
            "platform": self.platform,
            "author": self.author,
            "timestamp": self.timestamp,
            "text": self.text,
            "image_path": self.image_path
        }


# === Scraping Functions (mock / placeholder – you must implement real auth) ===
def scrape_instagram(username: str) -> List[Dict]:
    """
    Scrape Instagram public posts using instaloader.
    Install: pip install instaloader
    """
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
            # Limit for demo
            if len(items) >= 10:
                break
    except ImportError:
        print("[!] instaloader not installed. Skipping Instagram scraping.")
    except Exception as e:
        print(f"[!] Instagram error: {e}")
    return items


def scrape_discord(token: str, channel_id: str, limit: int = 50) -> List[Dict]:
    """
    Scrape Discord messages using a user token (self-bot – violates ToS).
    Only use on your own servers with permission.
    """
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


def scrape_twitter(username: str) -> List[Dict]:
    """
    Scrape Twitter (X) public tweets using unofficial API.
    For robust use, replace with twint or snscrape.
    """
    items = []
    # Using snscrape (requires pip install snscrape)
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
            if i >= 10:
                break
    except ImportError:
        print("[!] snscrape not installed. Skipping Twitter scraping.")
    except Exception as e:
        print(f"[!] Twitter error: {e}")
    return items


def scrape_reddit(username: str) -> List[Dict]:
    """
    Scrape Reddit using praw (requires API credentials) or simple RSS.
    Here using a basic requests + JSON fallback.
    """
    items = []
    url = f"https://www.reddit.com/user/{username}/submitted/.json?limit=10"
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


# === Normalization ===
def normalize_items(raw_items: List[Dict]) -> List[ContentItem]:
    normalized = []
    for item in raw_items:
        # Download image if URL exists (simplified)
        image_path = None
        if item.get("image_url"):
            # Placeholder: you would download and store locally
            # For demo, we skip image download.
            pass
        normalized.append(ContentItem(
            platform=item["platform"],
            author=item["author"],
            timestamp=item["timestamp"],
            text=item["text"],
            image_path=image_path
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
            options={"temperature": 0.1}  # low temp for deterministic output
        )
        raw = response["message"]["content"].strip()
        # Remove markdown code fences if present
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.endswith("```"):
            raw = raw[:-3]
        data = json.loads(raw)
        return data.get("secrets", [])
    except Exception as e:
        print(f"[!] LLM error on text: {e}")
        return []


def extract_secrets_from_image(image_path: str) -> str:
    """Optional: use vision model to describe sensitive content in image."""
    if not os.path.exists(image_path):
        return ""
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL_VISION,
            messages=[
                {"role": "user", "content": "Describe any sensitive information in this image: visible documents, computer screens, badges, signs, license plates, unique room layouts, reflections.",
                 "images": [image_path]}
            ]
        )
        return response["message"]["content"]
    except Exception as e:
        print(f"[!] Vision model error: {e}")
        return ""


# === Report Generation ===
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

    # Pretty print to console
    print("\n" + "="*60)
    print(f"BlackLight Report – {report['generated']}")
    print(f"Processed {items_processed} posts → Found {len(all_secrets)} secrets")
    for cat, secrets in report["secrets_by_category"].items():
        print(f"\n[{cat}] ({len(secrets)} items)")
        for s in secrets[:3]:  # show first 3 per category
            print(f"  • {s['text']} (confidence: {s.get('confidence', 'N/A')})")
    print(f"\nFull report saved to: {output_file}")
    print("="*60)


# === Main Orchestrator ===
def main():
    parser = argparse.ArgumentParser(description="BlackLight - AI-Powered Secret Extractor")
    parser.add_argument("--target", required=True, help="Username to investigate")
    parser.add_argument("--platforms", nargs="+", default=["instagram", "twitter", "reddit"],
                        help="Platforms to scrape (instagram, twitter, discord, reddit)")
    parser.add_argument("--discord-token", help="Discord user token (if scraping discord)")
    parser.add_argument("--discord-channel", help="Discord channel ID")
    parser.add_argument("--output", default="blacklight_report.json", help="Output JSON file")
    parser.add_argument("--no-images", action="store_true", help="Skip image analysis")
    args = parser.parse_args()

    # === Step 1: Scrape ===
    print(f"[*] Scraping {args.platforms} for target: {args.target}")
    raw_items = []
    if "instagram" in args.platforms:
        raw_items.extend(scrape_instagram(args.target))
    if "twitter" in args.platforms:
        raw_items.extend(scrape_twitter(args.target))
    if "reddit" in args.platforms:
        raw_items.extend(scrape_reddit(args.target))
    if "discord" in args.platforms:
        if not args.discord_token or not args.discord_channel:
            print("[!] Discord scraping requires --discord-token and --discord-channel")
        else:
            raw_items.extend(scrape_discord(args.discord_token, args.discord_channel))

    if not raw_items:
        print("[!] No content scraped. Check your credentials or platform availability.")
        sys.exit(1)

    print(f"[+] Scraped {len(raw_items)} posts/comments")

    # === Step 2: Normalize ===
    items = normalize_items(raw_items)
    print("[*] Normalized content for LLM processing")

    # === Step 3: Extract secrets ===
    all_secrets = []
    for idx, item in enumerate(items):
        print(f"[*] Processing item {idx+1}/{len(items)}: {item.platform} - {item.author}")
        secrets = extract_secrets_from_text(item.text)
        all_secrets.extend(secrets)

        # Optional image analysis
        if not args.no_images and item.image_path and os.path.exists(item.image_path):
            print(f"    Analyzing image: {item.image_path}")
            vision_desc = extract_secrets_from_image(item.image_path)
            if vision_desc:
                all_secrets.append({
                    "category": "VISUAL",
                    "text": vision_desc[:200],
                    "confidence": 0.8,
                    "evidence": f"Image from {item.platform}"
                })

    # === Step 4: Generate report ===
    generate_report(all_secrets, len(items), args.output)


if __name__ == "__main__":
    # Display legal warning
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  BLACKLIGHT – AI-Powered Secret Extractor                    ║
    ║  WARNING: Use only on accounts you own or have explicit     ║
    ║  permission to test. Unauthorized scraping violates ToS     ║
    ║  and may be illegal.                                        ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    main()