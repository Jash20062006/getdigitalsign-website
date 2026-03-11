"""
Get Digital Sign — Digital Signature Certificate Provider
Flask Application
"""
from flask import Flask, render_template, request, flash, redirect, url_for
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import csv
from datetime import datetime
from google_sheets import save_to_google_sheets

app = Flask(__name__)
app.secret_key = "get-digital-sign-secret-key-change-in-production"

# ─── DSC Pricing and Category Configuration ───
# This structure separates pricing from descriptive categories to prevent type errors
# when sorting dictionary items in Jinja templates.

# Categories associated with each certificate type
DSC_PRICING_CATEGORIES = {
    "Class 3 Signing": "INCOME TAX, GST, MCA",
    "Class 3 Only Org Signing": "ICEGATE",
    "Class 3 Combo": "TENDER",
    "DGFT": "DGFT",
    "Class 3 Foreign Only Signing": "INCOME TAX, GST",
}

# Prices for different validity periods (in years)
DSC_PRICES = {
    "Class 3 Signing": {1: 1400, 2: 1800, 3: 2500},
    "Class 3 Only Org Signing": {2: 2900, 3: 3800},
    "Class 3 Combo": {2: 3100, 3: 4200},
    "DGFT": {2: 3100, 3: 4200},
    "Class 3 Foreign Only Signing": {2: 7500, 3: 11000},
}


# ── Email Configuration ──
# IMPORTANT: For production, store credentials securely (e.g., environment variables)
# rather than hardcoding them in the source code.
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
GMAIL_USER = "dsc.getdigital@gmail.com"
GMAIL_APP_PASSWORD = "ywijfzcetxpveguh"
RECEIVER_EMAIL = "dsc.getdigital@gmail.com"

# CSV file paths
CSV_CONTACT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads_contact.csv")
CSV_APPLY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads_apply.csv")


def send_email(subject, body, reply_to=None):
    """Send an email via Gmail SMTP. Returns True on success."""
    if not GMAIL_APP_PASSWORD:
        print("[WARNING] GMAIL_APP_PASSWORD not set. Email not sent.")
        return False

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = RECEIVER_EMAIL
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False


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
        print(f"[ERROR] Failed to save CSV: {e}")
        return False


def send_contact_email(name, email, phone, subject, message):
    """Send contact form data via email and save to CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save to CSV
    _save_csv(
        CSV_CONTACT,
        ["Timestamp", "Name", "Email", "Phone", "Subject", "Message"],
        [timestamp, name, email, phone, subject, message],
    )

    # Save to Google Sheets
    try:
        save_to_google_sheets(name, email, phone, subject, message, "contact form")
    except Exception as e:
        print(f"[ERROR] Failed to save to Google Sheets from contact form: {e}")

    # Send email
    body = f"""New DSC Inquiry — Contact Form

Name:    {name}
Email:   {email}
Phone:   {phone or 'Not provided'}
Subject: {subject or 'Not provided'}

Message:
{message}

---
Submitted: {timestamp}
Source: Get Digital Sign Website — Contact Form
"""
    return send_email(
        f"New DSC Inquiry: {subject or 'Contact Form'}",
        body,
        reply_to=email,
    )


def send_apply_email(name, email, phone, pan, cert_type, validity, org_name, purpose):
    """Send apply form data via email and save to CSV."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Dynamically generate certificate label with price
    price_info = DSC_PRICES.get(cert_type, {})
    price = price_info.get(int(validity), "N/A")
    cert_label = f"{cert_type} ({validity} Year) - ₹{price}"


    # Save to CSV
    _save_csv(
        CSV_APPLY,
        ["Timestamp", "Name", "Email", "Phone", "PAN", "Certificate Type",
         "Validity", "Organization", "Purpose"],
        [timestamp, name, email, phone, pan, cert_label, validity, org_name, purpose],
    )

    # Save to Google Sheets
    try:
        subject = f"Application for {cert_label}"
        save_to_google_sheets(name, email, phone, subject, purpose, "apply form")
    except Exception as e:
        print(f"[ERROR] Failed to save to Google Sheets from apply form: {e}")

    # Send email
    body = f"""New DSC Application

Full Name:         {name}
Email:             {email}
Phone:             {phone}
PAN:               {pan or 'Not provided'}
Certificate Type:  {cert_label}
Validity:          {validity}
Organization:      {org_name or 'N/A (Individual)'}
Purpose:           {purpose or 'Not specified'}

---
Submitted: {timestamp}
Source: Get Digital Sign Website — Apply Form
"""
    return send_email(
        f"New DSC Application: {name}",
        body,
        reply_to=email,
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
            print(DSC_PRICES)
            return render_template("apply.html", prices=DSC_PRICES, form_data=request.form)

        # Send email + save to CSV
        send_apply_email(name, email, phone, pan, cert_type, validity, org_name, purpose)

        flash(
            "Thank you! Your DSC application has been submitted successfully. "
            "Our team will contact you shortly.",
            "success",
        )
        return redirect(url_for("apply"))

    print(DSC_PRICES)
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

        # Send email
        send_contact_email(name, email, phone, subject, message)

        flash(
            "Thank you! Our team will contact you shortly.",
            "success",
        )
        return redirect(url_for("contact"))



    return render_template("contact.html", form_data={})


# ──────────────────────────────────────────────
# Blog — 10 SEO Optimized Articles
# ──────────────────────────────────────────────

BLOG_POSTS = [
    {
        "slug": "what-is-digital-signature",
        "title": "What is a Digital Signature Certificate (DSC)? Complete Guide",
        "seo_title": "What is Digital Signature Certificate | Complete DSC Guide 2026",
        "meta_description": "Learn what a Digital Signature Certificate is, how it works, types of DSC, and how to apply for DSC online in India. Complete beginner guide.",
        "keywords": "Digital Signature Certificate, DSC India, what is DSC, digital signature, electronic signature India",
        "excerpt": "A Digital Signature Certificate is an electronic credential that authenticates your identity for secure online transactions. Learn everything about DSC — types, uses, and how to get one.",
        "date": "March 5, 2026",
        "author": "Get Digital Sign Team",
        "category": "Guides",
        "read_time": "8 min read",
        "content": """
<p>In today's digital-first world, verifying identity online is critical. A Digital Signature Certificate (DSC) is an electronic credential issued by a licensed Certifying Authority (CA) that serves as proof of identity for individuals and organizations conducting transactions over the internet. Think of it as the digital equivalent of a notarized physical signature — but significantly more secure, tamper-proof, and legally binding under Indian law.</p>

<p>Whether you are a chartered accountant filing tax returns, a business owner registering on a government procurement portal, or a startup founder incorporating a company, a DSC is an essential tool in modern India.</p>

<h2>How Does a Digital Signature Certificate Work?</h2>
<p>Digital Signature Certificates rely on Public Key Infrastructure (PKI). Every DSC contains a pair of keys: a private key stored securely on a physical USB token, and a public key embedded in your certificate. When you sign a document digitally, the software uses your private key to create a unique encrypted hash. The recipient uses your public key to verify the signature is authentic and the document is unaltered. This makes digital signatures extremely secure — any modification after signing instantly flags tampering.</p>

<h2>Why Do You Need a DSC in India?</h2>
<p>DSCs are required for income tax e-filing for companies, GST registration and return filing, filing documents with the Registrar of Companies (ROC) through MCA, participating in e-tendering and e-procurement on government platforms, patent and trademark applications through IP India, EPFO submissions, customs and DGFT filings for import-export businesses, and signing contracts electronically. Without a valid DSC, you cannot complete many of these processes.</p>

<h2>Types of Digital Signature Certificates</h2>
<p>The primary type of certificate available is Class 3, which offers the highest level of assurance and is suitable for a wide range of applications including income tax filing, GST, MCA, e-tendering, and more. Prices vary based on the certificate type and validity period. You can <a href="/services">view all certificate plans here</a>.</p>

<h2>How to Apply for a Digital Signature Certificate</h2>
<p>Getting a DSC with Get Digital Sign takes 30 minutes to 1 hour. Fill your application online, upload PAN and Aadhaar, complete video KYC, and receive your DSC on a secure USB token via express delivery. <a href="/apply">Apply for your DSC now</a>.</p>

<h2>Benefits of Digital Signature Certificates</h2>
<p>DSCs provide authentication confirming the signer's identity, integrity ensuring documents are unaltered, non-repudiation preventing signers from denying their signature, time savings eliminating physical document handling, and environmental benefits reducing paper use.</p>

<h2>Legal Status</h2>
<p>Digital signatures are fully legal under the Information Technology Act, 2000. Section 5 gives them the same standing as handwritten signatures. Documents signed with a valid DSC are legally enforceable in Indian courts. Read our <a href="/blog/legal-status-dsc">detailed legal guide</a>.</p>

<h2>Frequently Asked Questions</h2>
<h3>Is a DSC mandatory in India?</h3>
<p>Yes, for companies filing tax returns, GST, MCA documents, e-tendering, and patent applications. For individuals, it depends on income thresholds and filing requirements.</p>

<h3>How long does it take to get a DSC?</h3>
<p>Individual DSCs are issued within 30 minutes to 1 hour. Organization DSCs take 2 to 4 hours. <a href="/apply">Start your application here</a>.</p>

<h3>Can I use my DSC on multiple computers?</h3>
<p>Yes. The USB token is portable and works on any computer with the token driver installed.</p>

<h3>What happens if my DSC expires?</h3>
<p>An expired DSC cannot be used for signing. You must renew before expiry. We send reminders 30 days in advance.</p>

<h3>Is a Digital Signature the same as an Electronic Signature?</h3>
<p>No. A digital signature uses PKI cryptography and is legally stronger. An electronic signature can be any form of electronic consent and may not carry the same legal weight.</p>
""",
    },
    {
        "slug": "how-to-apply-dsc",
        "title": "How to Apply for DSC in India: Step-by-Step Guide (2026)",
        "seo_title": "How to Apply for DSC in India | Step-by-Step Guide 2026",
        "meta_description": "Step-by-step guide to applying for a Digital Signature Certificate in India. Documents needed, video KYC process, and get your DSC in 30 minutes.",
        "keywords": "apply for DSC, DSC application, how to get DSC, DSC online apply, Digital Signature application India",
        "excerpt": "Want to apply for a Digital Signature Certificate? This step-by-step guide walks you through the entire DSC application process in India for 2026.",
        "date": "March 3, 2026",
        "author": "Priya Sharma",
        "category": "How-To",
        "read_time": "7 min read",
        "content": """
<p>Applying for a Digital Signature Certificate in India has become significantly simpler. The entire process can be completed online in under an hour. This guide walks you through every step.</p>

<h2>Who Needs to Apply for a DSC?</h2>
<p>Chartered accountants filing returns, company directors filing with ROC, businesses filing GST, organizations in e-tendering, professionals filing patents or trademarks, and import-export businesses filing with DGFT and customs.</p>

<h2>Step 1: Choose the Right Certificate Type</h2>
<p>Select the appropriate certificate for your needs, such as Class 3 Signing for tax and GST, Class 3 Combo for tenders, or DGFT certificates for import-export. Prices are based on the type and validity. <a href="/services">Compare all plans</a>.</p>

<h2>Step 2: Gather Your Documents</h2>
<p>PAN card, Aadhaar card, passport-size photo, active email and mobile number. For organizations: company PAN, GST certificate, incorporation certificate, authorization letter. See our <a href="/blog/dsc-documents">complete documents checklist</a>.</p>

<h2>Step 3: Fill the Online Application</h2>
<p>Visit our <a href="/apply">application page</a> and enter your details. The form takes 2 minutes. Ensure your name matches your PAN exactly.</p>

<h2>Step 4: Complete Video Verification</h2>
<p>Show your PAN and Aadhaar to the camera, confirm your identity, and provide a live photograph. Takes 2-3 minutes from any device with a camera.</p>

<h2>Step 5: Receive Your DSC</h2>
<p>Your certificate is generated, loaded onto a USB token, and shipped via express courier. Most individual DSCs are issued within 30 minutes after video verification.</p>

<h2>After Receiving Your DSC</h2>
<p>Install the token driver, plug in the token, and start signing. We provide free remote installation support. See our <a href="/blog/install-dsc-token">installation guide</a>.</p>

<h2>Common Mistakes to Avoid</h2>
<p>Name mismatch between application and PAN, Aadhaar mobile not linked, blurry photograph, unstable internet during video KYC.</p>

<h2>Frequently Asked Questions</h2>
<h3>How long does the application process take?</h3>
<p>30 minutes to 1 hour for individuals. 2-4 hours for organizations.</p>

<h3>Can I apply from home?</h3>
<p>Yes, the entire process including video KYC can be done from home.</p>

<h3>What if video verification fails?</h3>
<p>Our team reschedules immediately. Common reasons: poor lighting, network issues, documents not visible.</p>

<h3>Do I need physical documents?</h3>
<p>No. All documents are verified digitally during video KYC.</p>

<h3>Can I track my application?</h3>
<p>Yes. You receive status updates via email and SMS at every stage.</p>
""",
    },
    {
        "slug": "dsc-documents",
        "title": "Documents Required for Digital Signature Certificate: Complete Checklist",
        "seo_title": "Documents Required for DSC | Complete Checklist 2026",
        "meta_description": "Complete list of documents required for DSC application in India. Individual and organization checklist with tips for fast approval.",
        "keywords": "DSC documents required, documents for digital signature, DSC application documents, DSC checklist",
        "excerpt": "Planning to apply for a DSC? Here is the complete document checklist for individuals and organizations with expert tips for fast approval.",
        "date": "February 28, 2026",
        "author": "Rahul Verma",
        "category": "How-To",
        "read_time": "6 min read",
        "content": """
<p>Incomplete documentation is the most common reason for DSC application delays. Having everything ready before starting ensures your certificate is issued in 30 minutes. This guide covers the complete checklist.</p>

<h2>Documents for Individual DSC</h2>
<p>PAN card — primary identity document, name must match application exactly. Aadhaar card — required for video KYC, mobile number must be linked. Passport-size photograph — recent, clear, JPEG format. Active email address — for certificate details and correspondence. Active mobile number — for OTP verification and status updates.</p>

<h2>Documents for Organization DSC</h2>
<p>All individual documents for the authorized signatory, plus: Company PAN card, GST registration certificate, Certificate of Incorporation or partnership deed, and authorization letter on company letterhead signed by a director or partner.</p>

<h2>Documents for DGFT DSC</h2>
<p>Standard individual documents plus IEC (Import Export Code) certificate and DGFT registration documents.</p>

<h2>Document Format Requirements</h2>
<p>PDF or JPEG format, under 2 MB per file, clearly readable, colored scans preferred, self-attested copies accepted for individuals.</p>

<h2>Tips for a Smooth Application</h2>
<p>Verify name spelling matches across PAN, Aadhaar, and application. Check Aadhaar mobile is active. Keep all documents in one folder. Ensure photograph is recent. Test camera and internet before video KYC. <a href="/apply">Start your application now</a>.</p>

<h2>Frequently Asked Questions</h2>
<h3>Do I need to submit physical documents?</h3>
<p>No. All verification is done digitally through video KYC.</p>

<h3>Can I use driving license instead of Aadhaar?</h3>
<p>No. Aadhaar is mandatory for video-based KYC per CCA guidelines.</p>

<h3>What if my PAN and Aadhaar names don't match?</h3>
<p>Correct the mismatch first through NSDL (PAN) or an Aadhaar enrollment center.</p>

<h3>Are self-attested copies accepted?</h3>
<p>Yes for individuals. Organization documents need company letterhead and stamp.</p>

<h3>Is a passport-size photo mandatory?</h3>
<p>Yes. A recent, clear photograph is required for identity verification.</p>
""",
    },
    {
        "slug": "class-3-dsc",
        "title": "Understanding Class 3 DSC: Which Type Do You Need?",
        "seo_title": "Understanding Class 3 DSC | Comparison Guide India",
        "meta_description": "Differences between various Class 3 DSCs. Learn which certificate type you need based on your use case, with pricing comparison.",
        "keywords": "Class 3 DSC, DSC comparison, DSC types India",
        "excerpt": "Confused between different Class 3 DSCs? This comparison explains the differences, use cases, and pricing to help you choose correctly.",
        "date": "February 25, 2026",
        "author": "Priya Sharma",
        "category": "Certificates",
        "read_time": "7 min read",
        "content": """
<p>Choosing the right Class 3 DSC is the first decision you face when applying. They differ in use cases and cost. This guide provides a clear comparison.</p>

<h2>What is a Class 3 DSC?</h2>
<p>Highest identity assurance, requires video-based KYC. Required for e-tendering on government portals, patent and trademark applications, EPFO and customs submissions, and high-value contract signing. Cost varies by type, starting from ₹1400 for 1 year.</p>

<h2>Key Differences Between Class 3 Types</h2>
<p><b>Class 3 Signing:</b> For individuals for Income Tax, GST, MCA. <br>
   <b>Class 3 Only Org Signing:</b> For organizations for ICEGATE. <br>
   <b>Class 3 Combo:</b> For tenders. <br>
   <b>DGFT:</b> For DGFT portal. <br>
   <b>Class 3 Foreign Only Signing:</b> For foreign individuals/organizations for Income Tax, GST.</p>


<h2>Which One Should You Choose?</h2>
<p>Choose the certificate that matches your specific need. If you are an individual filing taxes, "Class 3 Signing" is for you. If you are participating in tenders, you will need "Class 3 Combo". <a href="/services">View pricing</a>.</p>

<h2>Frequently Asked Questions</h2>

<h3>Is Class 3 mandatory for e-tendering?</h3>
<p>Yes. Most government e-procurement portals require a Class 3 Combo certificate.</p>

<h3>Which DSC do chartered accountants need?</h3>
<p>A Class 3 Signing certificate is generally sufficient for CAs for filing IT returns, GST and for ROC.</p>

<h3>Is the application process different for each type?</h3>
<p>The basic application process is the same. All Class 3 certificates require video KYC. All are handled seamlessly online at Get Digital Sign.</p>

<h3>Do all types come on USB tokens?</h3>
<p>Yes. All are issued on secure USB tokens with free delivery.</p>
""",
    },
    {
        "slug": "dsc-cost",
        "title": "Cost of Digital Signature Certificate in India: Pricing Guide 2026",
        "seo_title": "DSC Cost India 2026 | Digital Signature Certificate Price",
        "meta_description": "Complete DSC pricing for 2026. Class 2, Class 3, DGFT certificate costs with USB token and delivery. No hidden charges.",
        "keywords": "DSC cost India, digital signature price, Class 3 DSC price, DSC charges, digital signature certificate cost",
        "excerpt": "How much does a Digital Signature Certificate cost? Complete pricing guide covering Class 2, Class 3, DGFT, and organization DSCs with all charges explained.",
        "date": "February 22, 2026",
        "author": "Rahul Verma",
        "category": "Guides",
        "read_time": "6 min read",
        "content": """
<p>DSC pricing varies by certificate class, validity period, and provider. Some advertise low prices but add hidden token and delivery charges. This guide provides transparent pricing.</p>

<h2>Get Digital Sign Pricing (2026)</h2>
<p>Our pricing is transparent and all-inclusive. For example, a Class 3 Signing certificate starts at ₹1400 for 1 year. All prices include a secure USB token and free delivery. <a href="/services">View all plans</a>.</p>

<h2>What's Included in the Price?</h2>
<p>DSC issued by licensed CA, secure USB token, free express delivery across India, free installation support, dedicated phone/email/WhatsApp support, and renewal reminders. No hidden charges.</p>

<h2>Factors Affecting Cost</h2>
<p>Certificate class (Class 3 costs more due to video KYC), validity period (3-year costs more but better per-year value), individual vs organization, and bulk orders (10+ get volume discounts).</p>

<h2>How We Compare</h2>
<p>Some providers charge ₹500 base but add ₹300-500 for the token, ₹100-200 for delivery, and extra for support. Our all-inclusive pricing is typically cheaper when you add everything up.</p>

<h2>Tax Deductibility</h2>
<p>DSC expenses are tax-deductible as a business expense. Consult your CA for specific treatment.</p>

<h2>Frequently Asked Questions</h2>
<h3>Is the USB token included?</h3>
<p>Yes. All plans include the token at no extra cost.</p>

<h3>Is delivery free?</h3>
<p>Yes. Free express delivery anywhere in India.</p>

<h3>Is there a refund policy?</h3>
<p>Yes. Full refund if your application cannot be processed. <a href="/contact">Contact us</a> for details.</p>

<h3>Bulk discounts available?</h3>
<p>Yes. 10+ certificates qualify for volume pricing with a dedicated account manager.</p>

<h3>Is 3-year more cost-effective?</h3>
<p>Yes. Per-year cost is lower with 3-year validity.</p>
""",
    },
    {
        "slug": "dsc-validity",
        "title": "DSC Validity Period Explained: How Long Does a Digital Signature Last?",
        "seo_title": "DSC Validity Period | How Long is Digital Signature Valid",
        "meta_description": "DSC validity periods in India explained. How long does a digital signature last? What happens on expiry? Renewal guide included.",
        "keywords": "DSC validity, digital signature validity period, DSC expiry, how long DSC valid, DSC renewal period",
        "excerpt": "How long does a DSC remain valid? This guide explains validity periods, what happens on expiry, and how to ensure uninterrupted service.",
        "date": "February 18, 2026",
        "author": "Get Digital Sign Team",
        "category": "Guides",
        "read_time": "5 min read",
        "content": """
<p>Every DSC has a defined validity period after which it expires. Understanding this is important for planning renewals and avoiding business disruption.</p>

<h2>Standard Validity Periods</h2>
<p>2-year validity is the standard option. 3-year validity offers better per-year value. Validity starts from issuance date, not first use.</p>

<h2>What Happens When Your DSC Expires?</h2>
<p>It becomes non-functional immediately. You cannot sign documents, file tax returns, submit GST, or participate in e-tendering. Documents signed before expiry remain valid. Only new signatures are affected.</p>

<h2>How to Check Expiry Date</h2>
<p>Insert your USB token, open token management software, and check the "Valid To" date. Or check via Windows Internet Options > Content > Certificates.</p>

<h2>Renewal Process</h2>
<p>Submit renewal application, complete fresh video KYC, receive new certificate on your token. Takes 30 minutes to 1 hour. We send reminders at 30, 15, and 7 days before expiry. <a href="/blog/dsc-renewal">Read our renewal guide</a>.</p>

<h2>Can I Renew Early?</h2>
<p>Yes, but new validity starts from renewal date, not old expiry. We recommend renewing in the last 15-30 days.</p>

<h2>Frequently Asked Questions</h2>
<h3>Can I extend validity without renewal?</h3>
<p>No. You must apply for a new certificate through the renewal process.</p>

<h3>Do old signed documents become invalid?</h3>
<p>No. Documents signed before expiry remain legally valid indefinitely.</p>

<h3>How much does renewal cost?</h3>
<p>Same as a new certificate. <a href="/services">View pricing</a>.</p>

<h3>Can I renew with a different provider?</h3>
<p>Yes. Renewal is a new application and can be done with any licensed provider.</p>

<h3>Is there a grace period after expiry?</h3>
<p>No. Expired DSCs are immediately non-functional. Plan renewal in advance.</p>
""",
    },
    {
        "slug": "dsc-gst",
        "title": "How to Use DSC for GST Filing: Step-by-Step Guide",
        "seo_title": "How to Use DSC for GST Filing | Step-by-Step Guide",
        "meta_description": "Register and use your DSC on the GST portal. Step-by-step guide for DSC registration, return filing, and troubleshooting.",
        "keywords": "DSC for GST, GST filing DSC, digital signature GST portal, register DSC GST, GST return DSC",
        "excerpt": "Need to use your DSC for GST filing? Step-by-step guide for registering your digital signature on the GST portal and filing returns.",
        "date": "February 15, 2026",
        "author": "Priya Sharma",
        "category": "How-To",
        "read_time": "6 min read",
        "content": """
<p>A DSC is mandatory for GST registration and filing for companies and LLPs. This guide provides a complete walkthrough.</p>

<h2>Who Needs DSC for GST?</h2>
<p>All companies registered under Companies Act 2013, LLPs, foreign nationals registering for GST, and professionals filing on behalf of clients. For proprietors, DSC is optional but recommended. If you don't have one, <a href="/apply">apply here</a>.</p>

<h2>Prerequisites</h2>
<p>Valid DSC on USB token, token driver installed, emBridge or Signer utility installed, Chrome or Firefox browser, working internet.</p>

<h2>Step 1: Install USB Token Driver</h2>
<p>Download from the token manufacturer's website. Install and restart your computer. See our <a href="/blog/install-dsc-token">installation guide</a> for detailed steps.</p>

<h2>Step 2: Install Signer Utility</h2>
<p>Download the DSC Signer from the GST portal help section. Run as Administrator. Keep it running in background.</p>

<h2>Step 3: Register DSC on GST Portal</h2>
<p>Log in to gst.gov.in > My Profile > Register/Update DSC. Select your certificate, enter token password, click Register. Confirmation message appears on success.</p>

<h2>Step 4: File Returns with DSC</h2>
<p>Prepare your return, select DSC signing option at submission, enter token password, submit. The return is now digitally signed and legally valid.</p>

<h2>Troubleshooting</h2>
<p>Token not detected: check driver and USB port. Certificate mismatch: re-register DSC. Token locked: contact manufacturer for PUK code. <a href="/contact">Contact our support</a> for free remote help.</p>

<h2>Frequently Asked Questions</h2>
<h3>Can I use Class 2 DSC for GST?</h3>
<p>Yes. Both Class 2 and Class 3 are accepted on the GST portal.</p>

<h3>Do I register DSC every time I file?</h3>
<p>No. Register once, use for all subsequent filings until it expires.</p>

<h3>Can a CA file using their own DSC?</h3>
<p>No. The DSC must belong to the business's authorized signatory.</p>

<h3>What if DSC expires between filings?</h3>
<p>You cannot file until you register a new valid DSC. Renew 15 days before expiry.</p>

<h3>Is DSC mandatory for proprietors?</h3>
<p>No. Proprietors can use EVC (Aadhaar-based) instead, but DSC is recommended.</p>
""",
    },
    {
        "slug": "dsc-renewal",
        "title": "DSC Renewal Process in India: Complete Guide",
        "seo_title": "DSC Renewal Process India | Renew Digital Signature Online",
        "meta_description": "Complete DSC renewal guide. When to renew, documents needed, step-by-step process, pricing, and how to avoid expiry downtime.",
        "keywords": "DSC renewal, renew digital signature, DSC renewal process, DSC expiry renewal, renew DSC online",
        "excerpt": "Your DSC is expiring? Complete renewal guide covering when to renew, what documents you need, the process, and how to avoid downtime.",
        "date": "February 10, 2026",
        "author": "Anita Deshmukh",
        "category": "Guides",
        "read_time": "5 min read",
        "content": """
<p>DSCs are valid for 2 or 3 years. Once expired, they cannot be used. Timely renewal is essential to avoid disruption.</p>

<h2>When Should You Renew?</h2>
<p>Start 15-30 days before expiry. Get Digital Sign sends automatic reminders at 30, 15, and 7 days. Check expiry via token management software.</p>

<h2>Is Renewal Different from New Application?</h2>
<p>Same process but typically faster since your records exist. Submit renewal application, complete video KYC, receive new certificate. Key difference: faster processing with existing verified records.</p>

<h2>Documents Needed</h2>
<p>PAN card, Aadhaar with active mobile, recent photograph. For organizations: updated company documents if changed. See full <a href="/blog/dsc-documents">documents checklist</a>.</p>

<h2>Step-by-Step Renewal</h2>
<p>1. Visit <a href="/apply">application page</a> and select same certificate type. 2. Team verifies against existing records. 3. Complete video KYC. 4. New DSC generated on USB token. 5. Shipped via express delivery. Takes 30 minutes to 1 hour.</p>

<h2>Can I Renew on Same Token?</h2>
<p>Usually yes, if the token is functioning. If damaged or lost, a new token is provided at no extra cost.</p>

<h2>What if I Miss Renewal?</h2>
<p>Expired DSCs cannot be reactivated. You need a completely new application. There is no grace period.</p>

<h2>Renewal Pricing</h2>
<p>The renewal price is the same as applying for a new certificate. Please refer to our <a href="/services">services page</a> for the latest pricing. Bulk discounts for 10+ renewals are available. <a href="/contact">Contact for volume pricing</a>.</p>

<h2>Frequently Asked Questions</h2>
<h3>Can I renew early?</h3>
<p>Yes, but new validity starts from renewal date. Best to renew within 30 days of expiry.</p>

<h3>Is video KYC needed for renewal?</h3>
<p>Yes. Mandatory per CCA guidelines. Takes 2-3 minutes.</p>

<h3>Can I switch providers on renewal?</h3>
<p>Yes. You're not locked into any provider.</p>

<h3>Will my certificate serial number change?</h3>
<p>Yes. Re-register on portals like GST, e-tendering after renewal.</p>

<h3>Is there a grace period?</h3>
<p>No. Plan renewal in advance to avoid disruption.</p>
""",
    },
    {
        "slug": "install-dsc-token",
        "title": "How to Install DSC Token on Computer: Setup Guide",
        "seo_title": "Install DSC Token | USB Token Setup Guide Windows",
        "meta_description": "Step-by-step guide to installing your DSC USB token on Windows. Driver installation, certificate verification, and troubleshooting.",
        "keywords": "install DSC token, DSC USB token setup, DSC driver installation, how to install digital signature",
        "excerpt": "Just received your DSC USB token? Step-by-step guide to installing the driver, verifying your certificate, and getting ready to sign documents.",
        "date": "February 5, 2026",
        "author": "Get Digital Sign Team",
        "category": "How-To",
        "read_time": "6 min read",
        "content": """
<p>Before using your DSC, you need to install the token driver and verify the certificate is recognized. This guide covers the complete setup on Windows.</p>

<h2>What You Need</h2>
<p>DSC USB token, Windows 7 or later (10/11 recommended), available USB port, internet connection, token password/PIN. Do NOT insert the token until instructed.</p>

<h2>Step 1: Identify Token Model</h2>
<p>Common models: ePass 2003, Watchdata, Proxkey. Check the token body or dispatch email from Get Digital Sign.</p>

<h2>Step 2: Download Driver</h2>
<p>Visit manufacturer's website. Download driver matching your Windows version (32-bit or 64-bit). Check via right-click "This PC" > Properties.</p>

<h2>Step 3: Install Driver</h2>
<p>Close all browsers. Run installer as Administrator. Follow wizard with default settings. Restart your computer after installation.</p>

<h2>Step 4: Insert USB Token</h2>
<p>After restart, plug in the token. Windows should recognize it. LED light should activate. Allow any additional driver installation.</p>

<h2>Step 5: Verify Certificate</h2>
<p>Open token management software, enter PIN, check certificate details (name, issuer, validity). Or check via Windows Internet Options > Content > Certificates.</p>

<h2>Step 6: Test Signing</h2>
<p>Open a PDF in Adobe Reader, click Fill & Sign or Protect, select Sign with Certificate, choose your DSC, enter password. If successful, setup is complete.</p>

<h2>Troubleshooting</h2>
<p>Token not recognized: try different USB port, reinstall driver. No certificate showing: wrong driver or token needs re-initialization. Websites not detecting: install signer/emBridge utility. Token locked: contact manufacturer for PUK code. <a href="/contact">Free remote installation support available</a>.</p>

<h2>Frequently Asked Questions</h2>
<h3>Does it work on Mac/Linux?</h3>
<p>Primarily Windows. Some tokens have Mac drivers. Linux support is limited. Windows recommended for government portals.</p>

<h3>Can I use on multiple computers?</h3>
<p>Yes. Install driver on each computer, then the portable token works on all of them.</p>

<h3>What is the default password?</h3>
<p>Varies by model. Common: "12345678". Change immediately after first use.</p>

<h3>LED not lighting up?</h3>
<p>Try a different USB port (direct, not hub). If still dark, token may be defective — request replacement.</p>

<h3>Do e-tendering portals need extra software?</h3>
<p>Most require a Java-based signer or emBridge utility, downloadable from the portal's help section.</p>
""",
    },
    {
        "slug": "legal-status-dsc",
        "title": "Legal Status of Digital Signature in India: IT Act 2000 Guide",
        "seo_title": "Legal Status Digital Signature India | IT Act 2000",
        "meta_description": "Legal validity of digital signatures in India. IT Act 2000, court admissibility, regulatory framework, and legal enforcement guide.",
        "keywords": "legal status digital signature India, IT Act 2000, digital signature legal validity, DSC legal India",
        "excerpt": "Are digital signatures legally valid in India? Complete guide covering the IT Act 2000, court admissibility, and regulatory framework.",
        "date": "February 1, 2026",
        "author": "Rahul Verma",
        "category": "Guides",
        "read_time": "7 min read",
        "content": """
<p>Digital signatures have been legally recognized in India since 2000 and carry the same standing as handwritten signatures. This guide covers the complete legal framework.</p>

<h2>The Information Technology Act, 2000</h2>
<p>The IT Act is the primary legislation. Section 3 establishes digital signature authentication. Section 5 gives legal recognition — a digital signature satisfies any law requiring document authentication by signature. For all practical purposes, a DSC is legally equivalent to a handwritten signature.</p>

<h2>The IT Amendment Act, 2008</h2>
<p>Introduced electronic signatures as a broader category. However, PKI-based digital signatures from licensed CAs remain the gold standard for legal assurance.</p>

<h2>Controller of Certifying Authorities (CCA)</h2>
<p>Established under Section 17 of the IT Act. Licenses Certifying Authorities, sets standards, maintains the National Repository of Digital Certificates, and audits CAs. All DSCs from Get Digital Sign are issued through CCA-licensed authorities.</p>

<h2>Court Admissibility</h2>
<p>Section 65B of the Indian Evidence Act covers electronic records. Section 85B creates a presumption that digital signatures are valid unless proven otherwise — the burden of proof lies on the challenger. This significantly strengthens digitally signed documents.</p>

<h2>Where DSC is Legally Required</h2>
<p>Companies Act 2013 for MCA filings, GST Act for registration and filing, Income Tax Act for e-filing, Patent and Trademark Acts for applications, and various e-procurement rules for bid submissions.</p>

<h2>Limitations</h2>
<p>DSC cannot substitute for physical signatures on wills, certain negotiable instruments, powers of attorney requiring notarization, and some real estate transactions. For all other legal and business documents, DSC is fully valid.</p>

<h2>Frequently Asked Questions</h2>
<h3>Are digital signatures binding for contracts?</h3>
<p>Yes. Under the IT Act and Indian Contract Act, DSC-signed contracts are legally binding and enforceable.</p>

<h3>Can digitally signed documents be court evidence?</h3>
<p>Yes. Section 65B of the Evidence Act provides for admissibility with a presumption of validity.</p>

<h3>Is DSC stronger than electronic signature?</h3>
<p>Yes. PKI-based DSC from a licensed CA provides stronger legal assurance than simple electronic signatures.</p>

<h3>What about digital signature forgery?</h3>
<p>Extremely difficult due to PKI cryptography. Section 73A of the IT Act provides criminal penalties for fraudulent digital signatures.</p>

<h3>Do I need separate DSCs for each portal?</h3>
<p>No. One DSC works across all portals — income tax, GST, MCA, e-tendering. Register it separately on each. <a href="/apply">Get your legally valid DSC today</a>.</p>
""",
    },
]


@app.route("/blog")
def blog():
    return render_template("blog.html", posts=BLOG_POSTS)


@app.route("/blog/<slug>")
def blog_post(slug):
    post = next((p for p in BLOG_POSTS if p["slug"] == slug), None)
    if not post:
        return render_template("blog.html", posts=BLOG_POSTS), 404
    return render_template("blog_post.html", post=post, posts=BLOG_POSTS)


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)