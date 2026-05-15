"""
Utility functions for Real Jobs, Real People
"""
import secrets
import string
import logging
import bleach
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from twilio.rest import Client

logger = logging.getLogger(__name__)


def verify_turnstile(token, remote_ip=None):
    """
    Verify Cloudflare Turnstile CAPTCHA token.
    Returns True if verification passes, False otherwise.

    Set up at: https://dash.cloudflare.com/sign-up?to=/:account/turnstile
    """
    secret_key = getattr(settings, 'TURNSTILE_SECRET_KEY', '')

    # If Turnstile is not configured, allow through (for development)
    if not secret_key:
        logger.warning("Turnstile not configured - skipping verification")
        return True

    try:
        response = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret_key,
                'response': token,
                'remoteip': remote_ip
            },
            timeout=10
        )
        result = response.json()

        if result.get('success'):
            return True
        else:
            logger.warning(f"Turnstile verification failed: {result.get('error-codes', [])}")
            return False
    except Exception as e:
        logger.error(f"Turnstile verification error: {e}")
        # Fail open in case of network issues (configurable)
        return getattr(settings, 'TURNSTILE_FAIL_OPEN', True)

# Allowed HTML tags for job descriptions (XSS prevention)
ALLOWED_TAGS = ['p', 'br', 'strong', 'b', 'em', 'i', 'u', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'div']
ALLOWED_ATTRIBUTES = {'a': ['href', 'title'], 'span': ['class'], 'div': ['class']}


def sanitize_html(html_content):
    """
    Sanitize HTML content to prevent XSS attacks.
    Only allows safe tags and attributes.
    """
    if not html_content:
        return ''
    return bleach.clean(
        html_content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )


def generate_verification_code():
    """Generate a cryptographically secure 6-digit verification code"""
    # Use secrets module for cryptographic security instead of random
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def generate_2fa_code():
    """Generate a cryptographically secure 6-digit 2FA code"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def generate_verification_token():
    """Generate a cryptographically secure 64-character verification token for email"""
    return secrets.token_urlsafe(48)  # Generates ~64 chars of URL-safe base64


def send_phone_verification_code(phone_number, code):
    """
    Send verification code via SMS using Twilio

    Args:
        phone_number (str): Phone number to send code to
        code (str): 6-digit verification code

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        # Initialize Twilio client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        # Send SMS
        message = client.messages.create(
            body=f"Your Real Jobs, Real People verification code is: {code}. Valid for {settings.VERIFICATION_CODE_EXPIRY_MINUTES} minutes.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )

        return message.sid is not None

    except Exception as e:
        logger.error(f"Error sending SMS to {phone_number[:4]}****: {e}")
        return False


def send_2fa_code(phone_number, code):
    """
    Send 2FA login code via SMS using Twilio

    Args:
        phone_number (str): Phone number to send code to
        code (str): 6-digit 2FA code

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            body=f"Your Real Jobs, Real People login code is: {code}. Valid for 5 minutes. If you did not request this, please ignore.",
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )

        return message.sid is not None

    except Exception as e:
        logger.error(f"Error sending 2FA SMS to {phone_number[:4]}****: {e}")
        return False


def send_admin_traffic_notification(visit_info, method='email'):
    """
    Send notification to admin about new site traffic.

    Args:
        visit_info (dict): Information about the visit (ip, path, user_agent, etc.)
        method (str): 'email', 'sms', or 'both'

    Returns:
        bool: True if sent successfully
    """
    admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', None)
    admin_phone = getattr(settings, 'ADMIN_NOTIFICATION_PHONE', None)

    success = True

    if method in ('email', 'both') and admin_email:
        try:
            subject = f"New Visit: {visit_info.get('path', '/')}"
            message = f"""
New visitor on Real Jobs, Real People!

Time: {visit_info.get('time', 'Unknown')}
Page: {visit_info.get('path', '/')}
IP Address: {visit_info.get('ip', 'Unknown')}
User Agent: {visit_info.get('user_agent', 'Unknown')[:100]}
Referrer: {visit_info.get('referer', 'Direct')}
User: {visit_info.get('user', 'Anonymous')}

---
Real Jobs, Real People Traffic Monitor
            """
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Error sending traffic notification email: {e}")
            success = False

    if method in ('sms', 'both') and admin_phone:
        try:
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message = f"RJRP Visit: {visit_info.get('path', '/')} from {visit_info.get('ip', '?')} at {visit_info.get('time', 'now')}"
            # Truncate if too long
            if len(message) > 160:
                message = message[:157] + '...'

            client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=admin_phone
            )
        except Exception as e:
            logger.error(f"Error sending traffic notification SMS: {e}")
            success = False

    return success


def send_email_verification(user, token):
    """
    Send email verification link to user

    Args:
        user: User object
        token (str): Verification token

    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        from datetime import datetime
        current_year = datetime.now().year

        verification_link = f"{settings.SITE_URL}/verify-email/{token}/" if hasattr(settings, 'SITE_URL') else f"http://localhost:8000/verify-email/{token}/"

        subject = 'Verify your email - Real Jobs, Real People'

        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #7e512f 0%, #dda56c 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">Real Jobs, Real People</h1>
            </div>
            <div style="padding: 30px; background: #f5f0e5;">
                <h2 style="color: #7e512f;">Welcome, {user.first_name or user.username}!</h2>
                <p style="font-size: 16px; line-height: 1.6;">
                    Thank you for signing up with Real Jobs, Real People. To complete your registration,
                    please verify your email address by clicking the button below:
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}" style="background: #7e512f; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: bold;">
                        Verify Email Address
                    </a>
                </div>
                <p style="font-size: 14px; color: #666;">
                    Or copy and paste this link into your browser:<br>
                    <a href="{verification_link}" style="color: #7e512f;">{verification_link}</a>
                </p>
                <p style="font-size: 14px; color: #666; margin-top: 30px;">
                    This link will expire in 24 hours. If you didn't create an account, you can safely ignore this email.
                </p>
            </div>
            <div style="background: #7e512f; padding: 20px; text-align: center; color: white; font-size: 12px;">
                <p style="margin: 0;">&copy; {current_year} Real Jobs, Real People. All rights reserved.</p>
            </div>
        </body>
        </html>
        """

        plain_message = f"""
        Welcome to Real Jobs, Real People!

        Thank you for signing up. To complete your registration, please verify your email address by visiting:

        {verification_link}

        This link will expire in 24 hours.

        If you didn't create an account, you can safely ignore this email.

        Thanks,
        Real Jobs, Real People Team
        """

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return True

    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {e}")
        return False


def format_phone_number(phone):
    """
    Format phone number to E.164 format for Twilio

    Args:
        phone (str): Phone number in various formats

    Returns:
        str: Phone number in E.164 format (+1234567890)
    """
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))

    # If no country code, assume US (+1)
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"+{digits}"
    else:
        # Assume it already has country code
        return f"+{digits}"


def is_valid_phone_number(phone):
    """
    Validate phone number format

    Args:
        phone (str): Phone number to validate

    Returns:
        bool: True if valid, False otherwise
    """
    digits = ''.join(filter(str.isdigit, phone))
    # Must be 10 digits (US) or 11 digits (with country code)
    return len(digits) in [10, 11]


def generate_listing_summary(listing):
    """
    Generate a concise AI summary of a scraped job listing's description.
    Uses Claude Haiku for speed and cost-efficiency.

    Returns the summary text, or empty string on failure.
    Also saves the summary to the listing's description_summary field.
    """
    import re

    api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
    if not api_key:
        return ''

    description = listing.description or ''
    if not description or len(description) < 100:
        return ''

    # Strip HTML for the prompt
    plain = re.sub(r'<[^>]+>', ' ', description)
    plain = re.sub(r'\s+', ' ', plain).strip()

    # Truncate to ~3000 chars to keep costs low
    if len(plain) > 3000:
        plain = plain[:3000] + '...'

    try:
        import anthropic
        # 20s socket timeout so a slow/hung Anthropic response can't hold a
        # gunicorn worker for the full 30s request timeout.
        client = anthropic.Anthropic(api_key=api_key, timeout=20.0)

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""Summarize this job listing in 3-5 bullet points. Each bullet should be one concise line. Cover: what the role does, key requirements, and any notable perks/details. Do not use markdown headers. Use plain bullet points starting with •.

Job Title: {listing.title}
Company: {listing.company_name}

Description:
{plain}"""
            }]
        )

        summary = response.content[0].text.strip()

        # Save to the listing
        listing.description_summary = summary
        listing.save(update_fields=['description_summary'])

        return summary

    except Exception as e:
        logger.error(f"Failed to generate summary for listing {listing.id}: {e}")
        return ''


def build_workday_fallback_url(listing):
    """
    Build a fallback search URL for Workday-sourced listings.

    Workday direct job URLs are session-based and expire quickly.
    This constructs a search URL on the same Workday career portal
    using the job title, which is much more stable.

    Works for both standard Workday domains (*.myworkdayjobs.com)
    and custom career portals backed by Workday.
    """
    from urllib.parse import urlparse, quote_plus

    source_url = listing.source_url or ''
    parsed = urlparse(source_url)

    if not parsed.netloc:
        return None

    # Standard Workday pattern: company.wd5.myworkdayjobs.com/en-US/External/job/...
    # Fallback search: company.wd5.myworkdayjobs.com/en-US/External?q=<title>
    if 'myworkdayjobs.com' in parsed.netloc:
        # Extract the base path up to the career site section (e.g., /en-US/External)
        path_parts = [p for p in parsed.path.split('/') if p]
        # Typical structure: ['en-US', 'External', 'job', 'Location', 'Title_JR123']
        # We want everything up to the career site name (usually 2nd segment)
        base_parts = []
        for part in path_parts:
            if part.lower() in ('job', 'jobs', 'details'):
                break
            base_parts.append(part)
        base_path = '/'.join(base_parts)
        title_query = quote_plus(listing.title)
        return f'{parsed.scheme}://{parsed.netloc}/{base_path}?q={title_query}'

    # Custom Workday portal (e.g., careers.company.com backed by Workday)
    # Try company_careers_url first, fall back to domain root
    if listing.company_careers_url:
        base = listing.company_careers_url.rstrip('/')
    else:
        base = f'{parsed.scheme}://{parsed.netloc}'

    title_query = quote_plus(listing.title)
    return f'{base}?q={title_query}'


def build_google_jobs_fallback_url(listing):
    """
    Build a Google search URL as the ultimate fallback for any listing
    whose direct link or portal search may not work (Workday 406s, expired
    session URLs, etc.).

    Constructs: google.com/search?q="Job Title" "Company Name" careers apply
    This reliably surfaces the listing on the employer's actual career portal.
    """
    from urllib.parse import quote_plus

    title = listing.title or ''
    company = getattr(listing, 'company_name', '') or ''

    if not title:
        return None

    query = f'"{title}" "{company}" careers apply'
    return f'https://www.google.com/search?q={quote_plus(query)}'
