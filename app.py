"""
Get Digital Sign — Digital Signature Certificate Provider
Flask Application
"""
import logging
import os
from datetime import datetime, timedelta

from flask import (Flask, flash, redirect, render_template, request,
                   url_for)
from flask_wtf.csrf import CSRFProtect
from google_sheets import save_to_google_sheets
import csv

import supabase_client as db
from admin import admin_bp

app = Flask(__name__)

_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. Set it to a long random "
        "value before starting the app (e.g. generate one with: "
        "python -c \"import secrets; print(secrets.token_hex(32))\")."
    )
app.secret_key = _secret_key
app.permanent_session_lifetime = timedelta(days=7)
csrf = CSRFProtect(app)  # protects every POST/PUT/PATCH/DELETE; GET is unaffected
app.register_blueprint(admin_bp)

CONTACT = {
    'phoneDisplay': '+91 97681 46715',
    'phoneLink': 'tel:+919768146715',
    'callLink': 'tel:+919768146715',
    'whatsapp': 'https://wa.me/919768146715'
}

@app.context_processor
def inject_globals():
    return dict(CONTACT=CONTACT)

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

DSC_PRICING_CATEGORIES = {
    "Class 3 Signing": "INCOME TAX, GST, MCA",
    "Class 3 Only Org Signing": "ICEGATE",
    "Class 3 Combo": "TENDER",
    "DGFT": "DGFT",
    "Class 3 Foreign Only Signing": "INCOME TAX, GST",
}

DSC_PRICES = {
    "Class 3 Signing": {1: 1400, 2: 1800, 3: 2500},
    "Class 3 Only Org Signing": {2: 2900, 3: 3800},
    "Class 3 Combo": {2: 3100, 3: 4200},
    "DGFT": {2: 3100, 3: 4200},
    "Class 3 Foreign Only Signing": {2: 7500, 3: 11000},
}







# CSV file paths
CSV_CONTACT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads_contact.csv")
CSV_APPLY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads_apply.csv")


def _save_csv(filepath, headers, row_data):
    """Append a row to a CSV file, creating it with headers if needed."""
    file_exists = os.path.isfile(filepath)
    try:
        with open(filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(headers)
            writer.writerow(row_data)
        return True
    except Exception as e:
        logging.error(f"Failed to save CSV: {e}")
        return False


def save_contact_submission(name, email, phone, subject, message):
    """Save contact form data to Google Sheets and CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not save_to_google_sheets(name, email, phone, subject, message, "contact form"):
        logging.warning("Failed to save contact form data to Google Sheets.")

    _save_csv(
        CSV_CONTACT,
        ["Timestamp", "Name", "Email", "Phone", "Subject", "Message"],
        [timestamp, name, email, phone, subject, message],
    )


def save_apply_submission(name, email, phone, pan, cert_type, validity, org_name, purpose):
    """Save apply form data to Google Sheets and CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    price_info = DSC_PRICES.get(cert_type, {})
    price = price_info.get(int(validity), "N/A")
    cert_label = f"{cert_type} ({validity} Year) - ₹{price}"

    subject = f"Application for {cert_label}"
    if not save_to_google_sheets(name, email, phone, subject, purpose, "apply form"):
        logging.warning("Failed to save apply form data to Google Sheets.")
    
    _save_csv(
        CSV_APPLY,
        ["Timestamp", "Name", "Email", "Phone", "PAN", "Certificate Type",
         "Validity", "Organization", "Purpose"],
        [timestamp, name, email, phone, pan, cert_label, validity, org_name, purpose],
    )


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/services")
def services():
    return render_template("services.html", prices=DSC_PRICES, categories=DSC_PRICING_CATEGORIES)


@app.route("/apply", methods=["GET", "POST"])
def apply():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        pan = request.form.get("pan", "").strip()
        cert_type = request.form.get("cert_type", "").strip()
        validity = request.form.get("validity", "2").strip()
        org_name = request.form.get("org_name", "").strip()
        purpose = request.form.get("purpose", "").strip()

        errors = []
        if not name:
            errors.append("Full name is required.")
        if not email or "@" not in email:
            errors.append("A valid email address is required.")
        if not phone or len(phone) < 10:
            errors.append("A valid phone number is required.")
        if not cert_type:
            errors.append("Please select a certificate type.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("apply.html", prices=DSC_PRICES, form_data=request.form)

        save_apply_submission(name, email, phone, pan, cert_type, validity, org_name, purpose)
        
        flash(
            "Thank you! Your DSC application has been submitted successfully. "
            "Our team will contact you shortly.",
            "success",
        )
        return redirect(url_for("apply", success="1"))

    return render_template("apply.html", prices=DSC_PRICES, form_data={})


@app.route("/faq")
def faq():
    faqs = [
        {"q": "What is a Digital Signature Certificate (DSC)?",
         "a": "A Digital Signature Certificate is an electronic form of a signature that can be used to authenticate the identity of the sender of a message or the signer of a document. It is issued by a licensed Certifying Authority (CA) under the Information Technology Act, 2000."},
        {"q": "What are the different classes of DSC?",
         "a": "There are primarily two classes relevant today: Class 2 DSC is used for filing documents with the Registrar of Companies (ROC), Income Tax e-filing, and GST returns. Class 3 DSC provides a higher level of assurance and is used for e-tendering, e-procurement, and patent/trademark filings."},
        {"q": "What documents are required to obtain a DSC?",
         "a": "For individuals: PAN card, Aadhaar card, a passport-size photograph, and email/phone verification. For organizations: the above, plus a copy of the registration certificate, GST certificate, and an authorization letter."},
        {"q": "How long does it take to get a DSC?",
         "a": "With our streamlined process, most individual DSCs are issued within 30 minutes to 1 hour after successful document verification. Organization DSCs may take 2-4 hours depending on the verification process."},
        {"q": "What is the validity period of a DSC?",
         "a": "DSCs are typically issued with a validity of 2 years. You will need to renew your certificate before it expires to ensure uninterrupted service. We send renewal reminders 30 days in advance."},
        {"q": "Can I use my DSC on multiple devices?",
         "a": "Yes, your DSC is stored on a USB token that can be used on any compatible computer. Simply plug in the token, install the required drivers, and you are ready to sign documents on that machine."},
        {"q": "Is a DSC legally valid in India?",
         "a": "Absolutely. Digital signatures are legally recognized under the Information Technology Act, 2000. They carry the same legal standing as handwritten signatures for electronic documents."},
        {"q": "What happens if I lose my USB token?",
         "a": "If your USB token is lost or damaged, you must report it immediately so the certificate can be revoked. A new DSC will need to be issued on a replacement token. We offer expedited reissuance for existing customers."},
    ]
    return render_template("faq.html", faqs=faqs)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        errors = []
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        if not message:
            errors.append("Please enter your message.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("contact.html", form_data=request.form)

        save_contact_submission(name, email, phone, subject, message)
        
        flash(
            "Thank you! Our team will contact you shortly.",
            "success",
        )
        return redirect(url_for("contact"))



    return render_template("contact.html", form_data={})


# ──────────────────────────────────────────────
# Blog — fallback/seed content
#
# BLOG_POSTS intentionally starts empty. The 10 articles that used to live
# here were temporary demo/placeholder content and were removed on purpose
# — they were never migrated into Supabase.
#
# This list still serves two purposes:
#   1. migrate_blog_posts.py reads it as its seed source, for the future if
#      you ever want to bulk-import posts defined this way. With it empty,
#      running that script imports nothing.
#   2. If Supabase is not configured (or a query fails), /blog and
#      /blog/<slug> fall back to serving this list. Since it is empty, the
#      public blog correctly shows its "Coming Soon" empty state until
#      posts are published through the admin CMS (/admin/blogs).
# ──────────────────────────────────────────────

BLOG_POSTS = []


def _estimate_read_time(html_content):
    import re
    text = re.sub(r"<[^>]+>", " ", html_content or "")
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return f"{minutes} min read"


def _format_db_post(row):
    """Adapts a Supabase `blogs` row into the field shape blog.html /
    blog_post.html expect (same shape as the legacy BLOG_POSTS dicts)."""
    published_at = row.get("published_at") or row.get("created_at")
    date_str = ""
    if published_at:
        try:
            dt = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            date_str = dt.strftime("%B %d, %Y")
        except Exception:
            date_str = ""
    return {
        "id": row.get("id"),
        "slug": row.get("slug", ""),
        "title": row.get("title", ""),
        "seo_title": row.get("meta_title") or row.get("title", ""),
        "meta_description": row.get("meta_description") or row.get("excerpt", ""),
        "keywords": row.get("keywords", ""),
        "excerpt": row.get("excerpt", ""),
        "date": date_str,
        "author": row.get("author") or "Get Digital Sign Team",
        "category": row.get("category") or "Guides",
        "read_time": row.get("read_time") or _estimate_read_time(row.get("content", "")),
        "content": row.get("content", ""),
        "featured_image": row.get("featured_image"),
    }


@app.route("/blog")
def blog():
    db_posts = db.get_published_posts()
    if db_posts is not None:
        posts = [_format_db_post(p) for p in db_posts]
        if posts:
            return render_template("blog.html", posts=posts)
    return render_template("blog.html", posts=BLOG_POSTS)


@app.route("/blog/<slug>")
def blog_post(slug):
    if db.is_configured():
        row = db.get_post_by_slug(slug, published_only=True)
        if row:
            db_posts = db.get_published_posts() or []
            all_posts = [_format_db_post(p) for p in db_posts]
            post = _format_db_post(row)
            return render_template("blog_post.html", post=post, posts=all_posts)

    post = next((p for p in BLOG_POSTS if p["slug"] == slug), None)
    if not post:
        db_posts = db.get_published_posts()
        fallback_posts = [_format_db_post(p) for p in db_posts] if db_posts else BLOG_POSTS
        return render_template("blog.html", posts=fallback_posts), 404
    return render_template("blog_post.html", post=post, posts=BLOG_POSTS)


@app.route("/about")
def about():
    return render_template("about.html")


# ──────────────────────────────────────────────
# Policy Pages
# ──────────────────────────────────────────────

POLICY_LAST_UPDATED = datetime.now().strftime("%B %d, %Y")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html", updated_date=POLICY_LAST_UPDATED)


@app.route("/terms")
def terms():
    return render_template("terms.html", updated_date=POLICY_LAST_UPDATED)


@app.route("/refund")
def refund():
    return render_template("refund.html", updated_date=POLICY_LAST_UPDATED)


@app.route("/shipping")
def shipping():
    return render_template("shipping.html", updated_date=POLICY_LAST_UPDATED)


if __name__ == "__main__":
    app.run(debug=True, port=5000)