"""
URL configuration for jobboard project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.decorators.cache import cache_page

from jobs.sitemaps import StaticViewSitemap, VerifiedJobSitemap, ObservedJobSitemap

sitemaps = {
    'static': StaticViewSitemap,
    'verified-jobs': VerifiedJobSitemap,
    'observed-jobs': ObservedJobSitemap,
}


def robots_txt(request):
    """Serve robots.txt to allow search engine indexing"""
    # AI training / scraper bots to disallow. The 8 crawlers covered by
    # Cloudflare's managed robots.txt ("Instruct AI bot traffic with robots.txt")
    # are intentionally NOT listed here to avoid duplicate directives:
    #   GPTBot, ClaudeBot, CCBot, Google-Extended, Amazonbot, Bytespider,
    #   Applebot-Extended, Meta-ExternalAgent.
    # The entries below are AI bots that Cloudflare's managed list does NOT
    # cover, so we keep blocking them here regardless of the Cloudflare toggle.
    ai_bots = [
        "ChatGPT-User",
        "OAI-SearchBot",
        "Claude-Web",
        "anthropic-ai",
        "PerplexityBot",
        "Perplexity-User",
        "cohere-ai",
        "Diffbot",
        "FacebookBot",
        "Meta-ExternalFetcher",
    ]

    # Aggressive SEO / index crawlers that walk every /jobs/observed/ detail
    # page back-to-back (dozens/min, 24/7) and have driven the web worker to
    # its 512MB memory ceiling. They add no value to the site, so block fully.
    aggressive_crawlers = [
        "meta-webindexer",
        "AhrefsBot",
        "SemrushBot",
        "DotBot",
    ]

    lines = []
    for bot in ai_bots + aggressive_crawlers:
        lines.append(f"User-agent: {bot}")
        lines.append("Disallow: /")
        lines.append("")

    lines.extend([
        "User-agent: *",
        "Allow: /",
        "",
        "# Disallow admin and private areas",
        "Disallow: /admin/",
        "Disallow: /account/",
        "Disallow: /employer/",
        "Disallow: /recruiter/",
        "",
        f"Sitemap: https://realjobsrealpeople.net/sitemap.xml",
    ])
    return HttpResponse("\n".join(lines), content_type="text/plain")


urlpatterns = [
    path('robots.txt', cache_page(60 * 60)(robots_txt), name='robots_txt'),
    path('sitemap.xml', cache_page(60 * 60)(sitemap), {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # Social authentication
    path('directory/', include('directory.urls')),
    path('', include('jobs.urls')),
]

# Serve media files
# In development: served by Django
# In production: served by Django (temporary - should use cloud storage for scale)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler403 = 'jobs.views.ratelimited_error'
