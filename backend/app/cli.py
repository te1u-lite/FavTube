import argparse
from .db import get_conn, init_db


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

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
