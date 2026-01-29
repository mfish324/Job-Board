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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.decorators.cache import cache_page


def robots_txt(request):
    """Serve robots.txt to allow search engine indexing"""
    lines = [
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
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


urlpatterns = [
    path('robots.txt', cache_page(60 * 60)(robots_txt), name='robots_txt'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),  # Social authentication
    path('', include('jobs.urls')),
]

# Serve media files
# In development: served by Django
# In production: served by Django (temporary - should use cloud storage for scale)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler403 = 'jobs.views.ratelimited_error'
