"""
Middleware for Real Jobs, Real People
"""
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class BlockBadBotsMiddleware:
    """
    Short-circuit known abusive crawlers with a cheap 403 before any view, DB
    query, or template render runs.

    These SEO/index bots crawl every /jobs/observed/ page around the clock and
    have repeatedly driven the 512MB web worker to its memory ceiling. This is
    app-level defense-in-depth that works whether or not traffic is routed
    through Cloudflare's proxy, so keep it FIRST in MIDDLEWARE so a blocked
    request costs almost nothing.

    Matched case-insensitively as substrings of the User-Agent.
    """

    # Matched case-insensitively as substrings of the User-Agent.
    # IMPORTANT: 'facebookexternalhit' (Facebook link-preview unfurler) is
    # intentionally NOT here — we want share previews to work.
    BLOCKED_UA_SUBSTRINGS = (
        # Meta crawlers
        'meta-webindexer',
        'meta-externalagent',
        'meta-externalfetcher',
        'facebookbot',
        # SEO / index scrapers with no value to the site
        'ahrefsbot',
        'semrushbot',
        'dotbot',
        'mj12bot',
        # Large-scale crawlers / AI training bots
        'amazonbot',
        'amzn-searchbot',  # Amazon's search crawler — distinct UA token from amazonbot
        'bytespider',
        'gptbot',
        'claudebot',
        'ccbot',
        'perplexitybot',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        if ua and any(bot in ua for bot in self.BLOCKED_UA_SUBSTRINGS):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('Forbidden')
        return self.get_response(request)


class TrafficNotificationMiddleware:
    """
    Middleware to track site visits and notify admin of new traffic.

    Configure in settings.py:
    - TRAFFIC_NOTIFICATION_ENABLED = True/False
    - TRAFFIC_NOTIFICATION_METHOD = 'email', 'sms', or 'both'
    - ADMIN_NOTIFICATION_EMAIL = 'admin@example.com'
    - ADMIN_NOTIFICATION_PHONE = '+1234567890'
    - TRAFFIC_NOTIFICATION_EXCLUDE_PATHS = ['/static/', '/media/', '/admin/']
    - TRAFFIC_NOTIFICATION_COOLDOWN_MINUTES = 5  # Don't notify for same IP within X minutes
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Process the request
        response = self.get_response(request)

        # Check if traffic notifications are enabled
        if not getattr(settings, 'TRAFFIC_NOTIFICATION_ENABLED', False):
            return response

        # Skip certain paths (static files, admin, etc.)
        exclude_paths = getattr(settings, 'TRAFFIC_NOTIFICATION_EXCLUDE_PATHS', [
            '/static/', '/media/', '/admin/', '/favicon.ico', '/robots.txt',
            '/api/notifications/', '/api/chatbot/'
        ])

        path = request.path
        if any(path.startswith(excluded) for excluded in exclude_paths):
            return response

        # Skip non-successful responses
        if response.status_code >= 400:
            return response

        try:
            self._record_and_notify(request)
        except Exception as e:
            logger.error(f"Traffic notification error: {e}")

        return response

    def _get_client_ip(self, request):
        """Get the client's IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip

    def _record_and_notify(self, request):
        """Record the visit and send notification if appropriate"""
        from .models import SiteVisit
        from .utils import send_admin_traffic_notification
        from datetime import timedelta

        ip = self._get_client_ip(request)
        path = request.path
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        referer = request.META.get('HTTP_REFERER', '')[:500] or None
        user = request.user if request.user.is_authenticated else None

        # Check cooldown - don't spam notifications for same IP
        cooldown_minutes = getattr(settings, 'TRAFFIC_NOTIFICATION_COOLDOWN_MINUTES', 5)
        cooldown_time = timezone.now() - timedelta(minutes=cooldown_minutes)

        recent_visit = SiteVisit.objects.filter(
            ip_address=ip,
            visited_at__gte=cooldown_time
        ).exists()

        # Record the visit
        visit = SiteVisit.objects.create(
            ip_address=ip,
            path=path,
            user_agent=user_agent,
            referer=referer,
            user=user,
            notified=not recent_visit  # Only mark as notified if we actually notify
        )

        # Send notification if not in cooldown
        if not recent_visit:
            method = getattr(settings, 'TRAFFIC_NOTIFICATION_METHOD', 'email')
            visit_info = {
                'ip': ip,
                'path': path,
                'user_agent': user_agent,
                'referer': referer or 'Direct',
                'user': user.username if user else 'Anonymous',
                'time': timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
            }
            send_admin_traffic_notification(visit_info, method=method)
