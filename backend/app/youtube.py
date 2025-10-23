import os
import re
import requests
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parents[2] / ".env"  # app -> backend -> プロジェクトルート
load_dotenv(dotenv_path=str(env_path))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def parse_video_id_from_url(url: str) -> str | None:
    """
    対応: https://www.youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID
    戻り値: 11桁のvideoId or None
    """
    try:
        u = urlparse(url)
        host = (u.netloc or "").lower()
        if "youtu.be" in host:
            vid = u.path.lstrip("/")
            return vid if _VIDEO_ID_RE.match(vid) else None
        if "youtube.com" in host or "music.youtube.com" in host:
            # /watch?v=ID
            qs = parse_qs(u.query)
            if "v" in qs:
                vid = qs["v"][0]
                return vid if _VIDEO_ID_RE.match(vid) else None
            parts = [p for p in u.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live"):
                vid = parts[1]
                return vid if _VIDEO_ID_RE.match(vid) else None
        # すでに videoId だけが来た場合にも対応
        if _VIDEO_ID_RE.match(url.strip()):
            return url.strip()
    except Exception:
        return None
    return None


def fetch_video_meta(video_id: str) -> dict:
    """
    Youtube Data API でタイトルとサムネURLを取得
    返却: {"id": ..., "title": ..., "thumbnail_url": ...}
    例外: RuntimeError (キー未設定/HTTPエラー/NotFound)
    """
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY is not set in environment.")
    endpoint = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "id": video_id,
        "part": "snippet",
        "key": YOUTUBE_API_KEY,
        "maxWidth": 1280,
    }
    resp = requests.get(endpoint, params=params, timeout=10)
    if resp.status_code != 200:
        raise RuntimeError(f"Youtube API error: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    items = data.get("items", [])
    if not items:
        raise RuntimeError("Video not found or not accessible.")
    snip = items[0].get("snippet", {})
    thumbs = snip.get("thumbnails", {}) or {}
    # available の中から最大サイズっぽいものを選ぶ
    order = ["maxres", "standard", "high", "medium", "default"]
    thumb_url = None
    for k in order:
        if k in thumbs and "url" in thumbs[k]:
            thumb_url = thumbs[k]["url"]
            break
    return {
        "id": video_id,
        "title": snip.get("title"),
        "thumbnail_url": thumb_url,
    }


def fetch_youtube_title(video_id: str) -> str | None:
    """YouTube Data APIを使って動画タイトルを取得"""
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"
        res = requests.get(url, timeout=5)
        data = res.json()
        if "items" in data and len(data["items"]) > 0:
            return data["items"][0]["snippet"]["title"]
    except Exception as e:
        print("YouTube API error:", e)
    return None
