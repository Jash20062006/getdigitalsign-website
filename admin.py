"""
Admin blueprint: login-protected blog CMS (dashboard, editor, publish/unpublish,
delete, image upload). Session-based auth using ADMIN_USERNAME / ADMIN_PASSWORD
environment variables — no credentials are hardcoded in source.
"""
import logging
import os
import re
import secrets
from functools import wraps
from urllib.parse import urlsplit

import bleach
from flask import (Blueprint, flash, jsonify, redirect, render_template,
                    request, session, url_for)

import supabase_client as db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

ALLOWED_TAGS = [
    "p", "br", "h2", "h3", "h4", "strong", "b", "em", "i", "u",
    "ul", "ol", "li", "a", "img", "blockquote", "code", "pre", "hr", "span",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height"],
    "span": ["class"],
}
ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "svg"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def sanitize_content(html):
    return bleach.clean(html or "", tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


def safe_next_url(target, default):
    """Return `target` only if it is a same-site local path; otherwise `default`.
    Rejects absolute URLs, protocol-relative (//host), backslash tricks,
    control characters and anything with a scheme or host (javascript:, http:...)."""
    if not target or not isinstance(target, str):
        return default
    if any(ord(c) < 32 for c in target) or "\\" in target:
        return default
    if not target.startswith("/") or target.startswith("//"):
        return default
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return default
    return target


def admin_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin.login", next=request.path))
        return f(*args, **kwargs)
    return wrapped


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("is_admin"):
        return redirect(url_for("admin.dashboard"))

    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        flash("Admin login is not configured yet. Set ADMIN_USERNAME and ADMIN_PASSWORD.", "error")
        return render_template("admin/login.html")

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        valid = secrets.compare_digest(username, ADMIN_USERNAME) and secrets.compare_digest(password, ADMIN_PASSWORD)
        if valid:
            session.clear()
            session["is_admin"] = True
            session.permanent = True
            flash("Logged in.", "success")
            next_url = safe_next_url(request.args.get("next"), url_for("admin.dashboard"))
            return redirect(next_url)
        flash("Invalid username or password.", "error")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def dashboard():
    return redirect(url_for("admin.blogs_list"))


@admin_bp.route("/blogs")
@admin_required
def blogs_list():
    supabase_ready = db.is_configured()
    posts = db.get_all_posts_admin() if supabase_ready else []
    return render_template("admin/dashboard.html", posts=posts, supabase_ready=supabase_ready)


def _collect_form_data(existing=None):
    title = request.form.get("title", "").strip()
    slug_input = request.form.get("slug", "").strip()
    base_slug = db.slugify(slug_input or title)
    exclude_id = existing["id"] if existing else None
    slug = db.unique_slug(base_slug, exclude_id=exclude_id)

    data = {
        "title": title,
        "slug": slug,
        "excerpt": request.form.get("excerpt", "").strip(),
        "content": sanitize_content(request.form.get("content", "")),
        "author": request.form.get("author", "").strip() or "Get Digital Sign Team",
        "category": request.form.get("category", "").strip() or "Guides",
        "meta_title": request.form.get("meta_title", "").strip(),
        "meta_description": request.form.get("meta_description", "").strip(),
        "keywords": request.form.get("keywords", "").strip(),
        "read_time": request.form.get("read_time", "").strip(),
        "status": "published" if request.form.get("action") == "publish" else "draft",
    }
    return data


def _handle_image_upload(existing_url=None):
    file = request.files.get("featured_image")
    if not file or not file.filename:
        return existing_url
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        flash(f"Featured image must be one of: {', '.join(sorted(ALLOWED_IMAGE_EXT))}.", "error")
        return existing_url
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_BYTES:
        flash("Featured image must be under 5 MB.", "error")
        return existing_url
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "-", file.filename)
    path = f"{secrets.token_hex(8)}-{safe_name}"
    try:
        return db.upload_image(file, path)
    except Exception as e:
        logging.error(f"Featured image upload failed: {e}")
        flash("Image upload failed. The post was saved without changing the featured image.", "error")
        return existing_url


@admin_bp.route("/blogs/new", methods=["GET", "POST"])
@admin_required
def blog_new():
    if not db.is_configured():
        flash("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.", "error")
        return redirect(url_for("admin.blogs_list"))

    if request.method == "POST":
        data = _collect_form_data()
        if not data["title"] or not data["content"]:
            flash("Title and content are required.", "error")
            return render_template("admin/editor.html", post=data, mode="new")
        data["featured_image"] = _handle_image_upload()
        try:
            db.create_post(data)
        except Exception as e:
            logging.error(f"Failed to create post: {e}")
            flash("Failed to save post. Please try again.", "error")
            return render_template("admin/editor.html", post=data, mode="new")
        flash(f"Post {'published' if data['status'] == 'published' else 'saved as draft'}.", "success")
        return redirect(url_for("admin.blogs_list"))

    return render_template("admin/editor.html", post=None, mode="new")


@admin_bp.route("/blogs/<int:post_id>/edit", methods=["GET", "POST"])
@admin_required
def blog_edit(post_id):
    if not db.is_configured():
        flash("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.", "error")
        return redirect(url_for("admin.blogs_list"))

    existing = db.get_post_by_id(post_id)
    if not existing:
        flash("Post not found.", "error")
        return redirect(url_for("admin.blogs_list"))

    if request.method == "POST":
        data = _collect_form_data(existing=existing)
        if not data["title"] or not data["content"]:
            flash("Title and content are required.", "error")
            merged = {**existing, **data}
            return render_template("admin/editor.html", post=merged, mode="edit")
        data["featured_image"] = _handle_image_upload(existing_url=existing.get("featured_image"))
        try:
            db.update_post(post_id, data)
        except Exception as e:
            logging.error(f"Failed to update post {post_id}: {e}")
            flash("Failed to save post. Please try again.", "error")
            merged = {**existing, **data}
            return render_template("admin/editor.html", post=merged, mode="edit")
        flash(f"Post {'published' if data['status'] == 'published' else 'saved as draft'}.", "success")
        return redirect(url_for("admin.blogs_list"))

    return render_template("admin/editor.html", post=existing, mode="edit")


@admin_bp.route("/blogs/<int:post_id>/publish", methods=["POST"])
@admin_required
def blog_publish(post_id):
    try:
        db.update_post(post_id, {"status": "published"})
        flash("Post published.", "success")
    except Exception as e:
        logging.error(f"Failed to publish post {post_id}: {e}")
        flash("Failed to publish post.", "error")
    return redirect(url_for("admin.blogs_list"))


@admin_bp.route("/blogs/<int:post_id>/unpublish", methods=["POST"])
@admin_required
def blog_unpublish(post_id):
    try:
        db.update_post(post_id, {"status": "draft"})
        flash("Post unpublished.", "success")
    except Exception as e:
        logging.error(f"Failed to unpublish post {post_id}: {e}")
        flash("Failed to unpublish post.", "error")
    return redirect(url_for("admin.blogs_list"))


@admin_bp.route("/blogs/<int:post_id>/delete", methods=["POST"])
@admin_required
def blog_delete(post_id):
    try:
        db.delete_post(post_id)
        flash("Post deleted.", "success")
    except Exception as e:
        logging.error(f"Failed to delete post {post_id}: {e}")
        flash("Failed to delete post.", "error")
    return redirect(url_for("admin.blogs_list"))


@admin_bp.route("/upload-image", methods=["POST"])
@admin_required
def upload_image():
    """Used by the editor's inline-image toolbar button. Returns {url: ...}
    on success so the client-side editor can insert it into the content."""
    if not db.is_configured():
        return jsonify({"error": "Supabase is not configured."}), 503

    file = request.files.get("image")
    if not file or not file.filename:
        return jsonify({"error": "No image provided."}), 400

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify({"error": f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXT))}"}), 400

    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_BYTES:
        return jsonify({"error": "Image must be under 5 MB."}), 400

    safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "-", file.filename)
    path = f"{secrets.token_hex(8)}-{safe_name}"
    try:
        url = db.upload_image(file, path)
        return jsonify({"url": url})
    except Exception as e:
        logging.error(f"Inline image upload failed: {e}")
        return jsonify({"error": "Upload failed."}), 500
