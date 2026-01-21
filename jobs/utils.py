"""
Utility functions for Real Jobs, Real People
"""
import secrets
import string
import logging
import bleach
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from twilio.rest import Client

logger = logging.getLogger(__name__)

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
