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
        # Declared crawlers seen hammering /jobs/ (SiteVisit, Nov 2026)
        'elevenlabscrawler',
        'exasearchbot',
        'baiduspider',
        'tokenfoundrybot',
        'terncrawler',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        if ua and any(bot in ua for bot in self.BLOCKED_UA_SUBSTRINGS):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('Forbidden')
        return self.get_response(request)


class ObservedDetailRateLimitMiddleware:
    """
    Cheap per-IP rate limits on the scraper-favoured browse/detail paths.

    A scraper rotating Chrome user agents walks these pages continuously; each
    hit costs several DB queries on a small, I/O-bound database. In-memory
    sliding window (per gunicorn worker, so the effective limit is up to
    workers x LIMIT) -- no DB or cache round trip. Over the limit gets 429 with
    Retry-After, which well-behaved crawlers (Googlebot) honor.

    RULES are (path_prefix, limit_per_window); the first matching prefix wins,
    so the more specific /jobs/observed/ must come before /jobs/. Each rule has
    its own counters. The /jobs/ limit is deliberately generous: the split-pane
    UI fires a /jobs/preview/ request per row click.
    """

    RULES = (
        ('/jobs/observed/', 20),
        ('/jobs/', 60),
    )
    WINDOW = 60         # seconds
    MAX_TRACKED_IPS = 5000

    def __init__(self, get_response):
        self.get_response = get_response
        self._hits = {}  # (prefix, ip) -> list[float] of recent request times

    @staticmethod
    def _client_ip(request):
        # Rightmost X-Forwarded-For entry is the one appended by Render's
        # proxy; earlier entries are client-supplied and trivially spoofed.
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[-1].strip()
        return request.META.get('REMOTE_ADDR', '')

    def __call__(self, request):
        if request.method in ('GET', 'HEAD'):
            for prefix, limit in self.RULES:
                if request.path.startswith(prefix):
                    if self._over_limit(prefix, limit, self._client_ip(request)):
                        from django.http import HttpResponse
                        response = HttpResponse('Too many requests', status=429)
                        response['Retry-After'] = str(self.WINDOW)
                        return response
                    break
        return self.get_response(request)

    def _over_limit(self, prefix, limit, ip):
        import time
        now = time.monotonic()
        cutoff = now - self.WINDOW

        if len(self._hits) > self.MAX_TRACKED_IPS:
            self._hits = {
                k: v for k, v in self._hits.items() if v and v[-1] > cutoff
            }

        key = (prefix, ip)
        recent = [t for t in self._hits.get(key, ()) if t > cutoff]
        if len(recent) >= limit:
            self._hits[key] = recent
            return True
        recent.append(now)
        self._hits[key] = recent
        return False


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

    BOT_UA_TOKENS = (
        'bot', 'spider', 'crawl', 'slurp', 'scrapy', 'python-requests',
        'python-urllib', 'curl/', 'wget', 'go-http-client', 'httpclient',
        'headless', 'facebookexternalhit', 'preview',
    )

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

        # Don't log self-identified bots: they inflate the dashboard and every
        # row is a write (plus 2 index updates) on a tiny database.
        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        if not ua or any(tok in ua for tok in self.BOT_UA_TOKENS):
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
            # Rightmost = appended by Render's proxy; leftmost is spoofable.
            ip = x_forwarded_for.split(',')[-1].strip()
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
