import argparse
from .db import get_conn, init_db
from .youtube import parse_video_id_from_url, fetch_video_meta
import csv
import os
from pathlib import Path


def cmd_add(args):
    """動画を追加/更新 (タイトルやサムネは任意) """
    init_db()
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO videos(id, title, thumbnail_url)
        VALUES(?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            title=COALESCE(?, videos.title),
            thumbnail_url=COALESCE(?, videos.thumbnail_url),
            updated_at=datetime('now')
        """, (args.id, args.title, args.thumb, args.title, args.thumb))
    print(f"Saved: {args.id} (title={args.title or '-'}, thumb={args.thumb or '-'})")


def cmd_get(args):
    """1件取得して表示"""
    with get_conn() as conn:
        v = conn.execute("SELECT * FROM videos WHERE id=?", (args.id,)).fetchone()
        if not v:
            print("not found")
            return
        tags = [r["tag"] for r in conn.execute(
            "SELECT tag FROM video_tags WHERE video_id=?", (args.id,)).fetchall()]
    print({
        "id": v["id"],
        "title": v["title"],
        "thumbnail_url": v["thumbnail_url"],
        "rating": v["rating"],
        "note": v["note"],
        "tags": tags,
        "created_at": v["created_at"],
        "updated_at": v["updated_at"],
    })


def cmd_list(_args):
    """一覧表示 (簡易) """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, rating, created_at FROM videos ORDER BY created_at DESC").fetchall()
    for r in rows:
        print(f"{r['created_at']}  {r['id']}  {r['rating'] or '-'}  {r['title'] or ''}")

# --- URLから追加 (メタ自動取得) ---


def cmd_add_url(args):
    vid = parse_video_id_from_url(args.url)
    if not vid:
        print("ERROR: URL から videoId を抽出できませんでした。")
        return
    init_db()
    # メタ取得
    try:
        meta = fetch_video_meta(vid)
    except Exception as e:
        print(f"ERROR: {e}")
        return
    # まず upsert
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO videos(id, title, thumbnail_url)
        VALUES(?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            title=COALESCE(excluded.title, videos.title),
            thumbnail_url=COALESCE(excluded.thumbnail_url, videos.thumbnail_url),
            updated_at=datetime('now')
        """, (meta["id"], meta["title"], meta["thumbnail_url"]))
        # オプション: rating
        if args.rate is not None:
            conn.execute(
                "UPDATE videos SET rating=?, updated_at=datetime('now') WHERE id =?", (args.rate, vid))
        # オプション: tags
        if args.tags:
            tags = [t.strip() for t in args.tags.split(",") if t.strip()]
            for t in set(tags):
                conn.execute("INSERT OR IGNORE INTO video_tags(video_id, tag) VALUES(?,?)", (vid, t))

    print(
        f"Saved by URL: {vid} | title={meta['title']!r} | rate={args.rate or '-'} | tags={args.tags or '-'}")


def cmd_fetch_meta(args):
    try:
        meta = fetch_video_meta(args.id)
    except Exception as e:
        print(f"ERROR: {e}")
        return
    with get_conn() as conn:
        conn.execute("""
        INSERT INTO videos(id, title, thumbnail_url)
        VALUES(?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            thumbnail_url=excluded.thumbnail_url,
            updated_at=datetime('now')
        """, (meta["id"], meta["title"], meta["thumbnail_url"]))
    print(f"Updated meta: {args.id} -> {meta['title']!r}")


def cmd_rate(args):
    if not (1 <= args.rating <= 5):
        print("ERROR: rating must be between 1..5")
        return
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE videos SET rating=?, updated_at=datetime('now') WHERE id=?", (args.rating, args.id))
    if cur.rowcount == 0:
        print("ERROR: video not found")
    else:
        print(f"Rated: {args.id} -> {args.rating}")


def cmd_tag_add(args):
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    with get_conn() as conn:
        for t in set(tags):
            conn.execute("INSERT OR IGNORE INTO video_tags(video_id, tag) VALUES(?,?)", (args.id, t))
        conn.execute("UPDATE videos SET updated_at=datetime('now') WHERE id=?", (args.id,))
    print(f"Tag added: {args.id} +{tags}")


def cmd_tag_rm(args):
    with get_conn() as conn:
        conn.execute("DELETE FROM video_tags WHERE video_id=? AND tag=?", (args.id, args.tag))
        conn.execute("UPDATE videos SET updated_at=datetime('now') WHERE id=?", (args.id,))
    print(f"Tag removed: {args.id} -{args.tag}")


# ---- CSV エクスポート ----
def cmd_export_csv(args):
    outdir = Path(args.dir)
    outdir.mkdir(parents=True, exist_ok=True)

    # videos.csv
    with get_conn() as conn, open(outdir / "videos.csv", "w", newline="", encoding="utf-8-sig")as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "thumbnail_url", "rating", "note", "created_at", "updated_at"])
        for r in conn.execute("SELECT id,title,thumbnail_url,rating,note,created_at,updated_at FROM videos ORDER BY created_at DESC"):
            w.writerow([r["id"], r["title"], r["thumbnail_url"], r["rating"],
                       r["note"], r["created_at"], r["updated_at"]])

    # video_tags.csv
    with get_conn() as conn, open(outdir / "video_tags.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "tag"])
        for r in conn.execute("SELECT video_id, tag FROM video_tags ORDER BY video_id, tag"):
            w.writerow([r["video_id"], r["tag"]])

    print(f"Exported to: {outdir}\\videos.csv, {outdir}\\video_tags.csv")

# ---- CSV インポート ----


def cmd_import_csv(args):
    indir = Path(args.dir)
    vids_csv = indir / "videos.csv"
    tags_csv = indir / "video_tags.csv"
    if not vids_csv.exists():
        print(f"ERROR: {vids_csv} not found")
        return

    with get_conn() as conn:
        # videos.csv
        with open(vids_csv, newline="", encoding="utf-8-sig")as f:
            reader = csv.DictReader(f)
            n = 0
            for row in reader:
                rating = row.get("rating")
                rating_val = int(rating) if (rating and rating.strip().isdigit())else None
                conn.execute("""
                INSERT INTO videos(id,title,thumbnail_url,rating,note,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  title=excluded.title,
                  thumbnail_url=excluded.thumbnail_url,
                  rating=excluded.rating,
                  note=excluded.note,
                  updated_at=datetime('now')
                """, (
                    row.get("id"), row.get("title"), row.get("thumbnail_url"),
                    rating_val, row.get("note"),
                    row.get("created_at") or None,  # created_atは渡されれば使う
                    row.get("updated_at") or None
                ))
                n += 1
            print(f"Imported videos: {n}")

        # video_tags.csv
        if tags_csv.exists():
            with open(tags_csv, newline="", encoding="utf-8-sig")as f:
                reader = csv.DictReader(f)
                m = 0
                skipped = 0
                for row in reader:
                    vid = row.get("video_id")
                    tag = (row.get("tag") or "").strip()
                    if not vid or not tag:
                        continue
                    # videos に存在しなければスキップ
                    v = conn.execute("SELECT 1 FROM videos WHERE id=?", (vid,)).fetchone()
                    if not v:
                        skipped += 1
                        continue
                    conn.execute(
                        "INSERT OR IGNORE INTO video_tags(video_id, tag) VALUES(?,?)", (vid, tag))
                    m += 1
                print(f"Imported tags: {m} (skipped without video: {skipped})")


def main():
    p = argparse.ArgumentParser(prog="favtube")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="動画を追加/更新")
    a.add_argument("id", help="Youtube videoId (例: dQw4w9WgXcQ)")
    a.add_argument("--title", help="任意のタイトル", default=None)
    a.add_argument("--thumb", help="任意のサムネURL", default=None)
    a.set_defaults(func=cmd_add)

    g = sub.add_parser("get", help="動画1件を表示")
    g.add_argument("id")
    g.set_defaults(func=cmd_get)

    l = sub.add_parser("list", help="一覧表示")
    l.set_defaults(func=cmd_list)

    # URL から登録
    au = sub.add_parser("add-url", help="URLから追加 (メタ自動取得、任意で★/タグ) ")
    au.add_argument("url", help="Youtube URL or videoId")
    au.add_argument("--rate", type=int, default=None, help="1..5")
    au.add_argument("--tags", type=str, default=None, help="カンマ区切り: 例 'music,80s'")
    au.set_defaults(func=cmd_add_url)

    # メタだけ更新
    fm = sub.add_parser("fetch-meta", help="既存IDのメタ情報をYoutubeから更新")
    fm.add_argument("id")
    fm.set_defaults(func=cmd_fetch_meta)

    # ★
    r = sub.add_parser("rate", help="★を設定")
    r.add_argument("id")
    r.add_argument("rating", type=int, help="1..5")
    r.set_defaults(func=cmd_rate)

    # タグ
    ta = sub.add_parser("tag-add", help="タグを追加")
    ta.add_argument("id")
    ta.add_argument("tags", help="カンマ区切り")
    ta.set_defaults(func=cmd_tag_add)

    tr = sub.add_parser("tag-rm", help="タグを1件削除")
    tr.add_argument("id")
    tr.add_argument("tag")
    tr.set_defaults(func=cmd_tag_rm)

    ex = sub.add_parser("export-csv", help="CSVインポート")
    ex.add_argument("--dir", default="backup")
    ex.set_defaults(func=cmd_export_csv)

    im = sub.add_parser("import-csv", help="CSVインポート")
    im.add_argument("--dir", default="backup")
    im.set_defaults(func=cmd_import_csv)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
