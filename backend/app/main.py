from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .youtube import parse_video_id_from_url, fetch_video_meta
from typing import List, Optional
import os

from .db import get_conn, init_db

app = FastAPI(title="FavTube")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class VideoUpsert(BaseModel):
    id: str
    title: Optional[str] = None
    thumbnail_url: Optional[str] = None


class RatingIn(BaseModel):
    rating: int


class TagsIn(BaseModel):
    tags: List[str]


class NoteIn(BaseModel):
    note: str


class AddUrlIn(BaseModel):
    url: str
    rate: int | None = None
    tags: list[str] | None = None


@app.post("/videos/add-url")
def add_by_url(body: AddUrlIn):
    vid = parse_video_id_from_url(body.url)
    if not vid:
        raise HTTPException(400, "invalid url")
    meta = fetch_video_meta(vid)
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO videos(id, title, thumbnail_url)
        VALUES(?,?,?)
        ON CONFLICT(id) DO UPDATE SET
        title=COALESCE(excluded.title, videos.title),
        thumbnail_url=COALESCE(excluded.thumbnail_url, videos.thumbnail_url),
        updated_at=datetime('now')
        """, (meta["id"], meta["title"], meta["thumbnail_url"]))
        if body.rate:
            conn.execute(
                "UPDATE videos SET rating=?, updated_at=datetime('now') WHERE id=?", (body.rate, vid))
        if body.tags:
            for t in set(body.tags):
                conn.execute("INSERT OR IGNORE INTO video_tags(video_id, tag) VALUES(?,?)", (vid, t))
    return {"ok": True, "id": vid, "title": meta["title"]}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/videos")
def list_videos(query: str = "", tag: str = "", order: str = "-created"):
    sql = "SELECT * FROM videos"
    params = []
    where = []
    if query:
        where.append("title LIKE ?")
        params.append(f"%{query}%")
    if tag:
        sql = "SELECT v.* FROM videos v JOIN video_tags t ON v.id=t.video_id"
        where.append("t.tag = ?")
        params.append(tag)
    if where:
        sql += " WHERE " + " AND ".join(where)
    if order == "-created":
        sql += " ORDER BY created_at DESC"
    elif order == "title":
        sql += " ORDER BY title ASC"
    elif order == "-rating":
        sql += " ORDER BY rating DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.get("/videos/{id}")
def get_video(id: str):
    with get_conn() as conn:
        v = conn.execute("SELECT * FROM videos WHERE id=?", (id,)).fetchone()
        if not v:
            raise HTTPException(404, "not found")
        tags = [r["tag"] for r in conn.execute(
            "SELECT tag FROM video_tags WHERE video_id=?", (id,)).fetchall()]
    d = dict(v)
    d["tags"] = tags
    return d


@app.post("/videos")
def upsert_video(v: VideoUpsert):
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO videos(id, title, thumbnail_url)
        VALUES(?,?,?)
        ON CONFLICT(id) DO UPDATE SET
          title=COALESCE(excluded.title, videos.title),
          thumbnail_url=COALESCE(excluded.thumbnail_url, videos.thumbnail_url),
          updated_at=datetime('now')
        """, (v.id, v.title, v.thumbnail_url))
    return {"ok": True}


@app.post("/videos/{id}/rating")
def set_rating(id: str, body: RatingIn):
    if not (1 <= body.rating <= 5):
        raise HTTPException(400, "rating must be 1..5")
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE videos SET rating=?, updated_at=datetime('now') WHERE id=?", (body.rating, id))
        if cur.rowcount == 0:
            raise HTTPException(404, "video not found")
    return {"ok": True}


@app.post("/videos/{id}/tags")
def add_tags(id: str, body: TagsIn):
    with get_conn() as conn:
        for t in set(body.tags):
            conn.execute("INSERT OR IGNORE INTO video_tags(video_id, tag) VALUES(?,?)", (id, t))
        conn.execute("UPDATE videos SET updated_at=datetime('now') WHERE id=?", (id,))
    return {"ok": True}


@app.delete("/videos/{id}/tags/{tag}")
def remove_tag(id: str, tag: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM video_tags WHERE video_id=? AND tag=?", (id, tag))
        conn.execute("UPDATE videos SET updated_at=datetime('now') WHERE id=?", (id,))
    return {"ok": True}


@app.post("/videos/{id}/note")
def set_note(id: str, body: NoteIn):
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE videos SET note=?, updated_at=datetime('now') WHERE id=?", (body.note, id))
        if cur.rowcount == 0:
            raise HTTPException(404, "video not found")
    return {"ok": True}
