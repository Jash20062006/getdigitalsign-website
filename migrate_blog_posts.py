"""
One-time migration: imports the 10 original hardcoded blog posts (BLOG_POSTS
in app.py) into the Supabase `blogs` table as published posts.

Usage:
    1. Run supabase_migration.sql in your Supabase project's SQL Editor.
    2. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (e.g. in a local .env
       file, or export them in your shell).
    3. python migrate_blog_posts.py

Safe to re-run: existing rows are matched by slug and left untouched by
default. Pass --update-existing to overwrite rows that already exist.
"""
import argparse
import sys
from datetime import datetime, timezone

import supabase_client as db
from app import BLOG_POSTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-existing", action="store_true",
                         help="Overwrite posts that already exist (matched by slug).")
    args = parser.parse_args()

    if not db.is_configured():
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set. Nothing to do.")
        sys.exit(1)

    client = db.get_client()
    created, updated, skipped = 0, 0, 0

    for post in BLOG_POSTS:
        row = {
            "title": post["title"],
            "slug": post["slug"],
            "excerpt": post.get("excerpt", ""),
            "content": post.get("content", ""),
            "author": post.get("author", "Get Digital Sign Team"),
            "category": post.get("category", "Guides"),
            "meta_title": post.get("seo_title", post["title"]),
            "meta_description": post.get("meta_description", post.get("excerpt", "")),
            "keywords": post.get("keywords", ""),
            "read_time": post.get("read_time", ""),
            "status": "published",
        }

        existing = db.get_post_by_slug(post["slug"], published_only=False)
        if existing:
            if args.update_existing:
                client.table("blogs").update(row).eq("id", existing["id"]).execute()
                updated += 1
                print(f"Updated: {post['slug']}")
            else:
                skipped += 1
                print(f"Skipped (already exists): {post['slug']}")
            continue

        # Preserve the original article's date as published_at where possible.
        try:
            dt = datetime.strptime(post.get("date", ""), "%B %d, %Y").replace(tzinfo=timezone.utc)
            row["published_at"] = dt.isoformat()
        except (ValueError, TypeError):
            row["published_at"] = datetime.now(timezone.utc).isoformat()

        client.table("blogs").insert(row).execute()
        created += 1
        print(f"Created: {post['slug']}")

    print(f"\nDone. Created: {created}, Updated: {updated}, Skipped: {skipped}.")


if __name__ == "__main__":
    main()
