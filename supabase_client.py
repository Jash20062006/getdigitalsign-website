"""
Supabase client and blog data-access helpers.

Every function here is safe to call even when Supabase is not configured
(SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set, or the `supabase` package
not installed) — reads return None/empty instead of raising, so the public
site can fall back to the hardcoded BLOG_POSTS seed data. Write operations
raise RuntimeError if called while unconfigured, since there is nowhere to
write to.
"""
import logging
import os
import re
from datetime import datetime, timezone

try:
    from supabase import create_client
except ImportError:
    create_client = None

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
BLOG_IMAGES_BUCKET = "blog-images"

_client = None


def is_configured():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and create_client)


def get_client():
    global _client
    if not is_configured():
        return None
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _client


# ── Slugs ──────────────────────────────────────────────

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "post"


def unique_slug(base_slug, exclude_id=None):
    """Returns base_slug, or base_slug-2/-3/... if already taken."""
    client = get_client()
    if not client:
        return base_slug
    candidate = base_slug
    n = 2
    while slug_exists(candidate, exclude_id=exclude_id):
        candidate = f"{base_slug}-{n}"
        n += 1
    return candidate


def slug_exists(slug, exclude_id=None):
    client = get_client()
    if not client:
        return False
    try:
        res = client.table("blogs").select("id").eq("slug", slug).execute()
        rows = res.data or []
        if exclude_id is not None:
            rows = [r for r in rows if str(r["id"]) != str(exclude_id)]
        return len(rows) > 0
    except Exception as e:
        logging.error(f"Supabase slug_exists failed: {e}")
        return False


# ── Reads ──────────────────────────────────────────────

def get_published_posts():
    """Returns a list of published posts (newest first), or None if Supabase
    is not configured / the query failed — callers should fall back to
    BLOG_POSTS in that case."""
    client = get_client()
    if not client:
        return None
    try:
        res = (
            client.table("blogs")
            .select("*")
            .eq("status", "published")
            .order("published_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception as e:
        logging.error(f"Supabase get_published_posts failed: {e}")
        return None


def get_post_by_slug(slug, published_only=True):
    client = get_client()
    if not client:
        return None
    try:
        q = client.table("blogs").select("*").eq("slug", slug)
        if published_only:
            q = q.eq("status", "published")
        res = q.limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None
    except Exception as e:
        logging.error(f"Supabase get_post_by_slug failed: {e}")
        return None


def get_all_posts_admin():
    client = get_client()
    if not client:
        return []
    try:
        res = client.table("blogs").select("*").order("updated_at", desc=True).execute()
        return res.data or []
    except Exception as e:
        logging.error(f"Supabase get_all_posts_admin failed: {e}")
        return []


def get_post_by_id(post_id):
    client = get_client()
    if not client:
        return None
    try:
        res = client.table("blogs").select("*").eq("id", post_id).limit(1).execute()
        rows = res.data or []
        return rows[0] if rows else None
    except Exception as e:
        logging.error(f"Supabase get_post_by_id failed: {e}")
        return None


# ── Writes ─────────────────────────────────────────────

def create_post(data):
    client = get_client()
    if not client:
        raise RuntimeError("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing).")
    if data.get("status") == "published" and not data.get("published_at"):
        data["published_at"] = datetime.now(timezone.utc).isoformat()
    res = client.table("blogs").insert(data).execute()
    return res.data[0] if res.data else None


def update_post(post_id, data):
    client = get_client()
    if not client:
        raise RuntimeError("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing).")
    if data.get("status") == "published":
        existing = get_post_by_id(post_id)
        if existing and not existing.get("published_at"):
            data["published_at"] = datetime.now(timezone.utc).isoformat()
    res = client.table("blogs").update(data).eq("id", post_id).execute()
    return res.data[0] if res.data else None


def delete_post(post_id):
    client = get_client()
    if not client:
        raise RuntimeError("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing).")
    client.table("blogs").delete().eq("id", post_id).execute()


# ── Storage (blog images) ─────────────────────────────

def upload_image(file_storage, filename):
    """Uploads a werkzeug FileStorage to the blog-images bucket and returns
    its public URL."""
    client = get_client()
    if not client:
        raise RuntimeError("Supabase is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY missing).")
    file_bytes = file_storage.read()
    content_type = file_storage.mimetype or "application/octet-stream"
    client.storage.from_(BLOG_IMAGES_BUCKET).upload(
        filename, file_bytes, {"content-type": content_type, "upsert": "true"}
    )
    return client.storage.from_(BLOG_IMAGES_BUCKET).get_public_url(filename)
