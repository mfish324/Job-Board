# CLAUDE.md - Project Guide for AI Assistants

## Project Overview

**Real Jobs, Real People (RJRP)** - A Django-based job board platform that connects job seekers with employers and recruiters. The platform emphasizes verified users and vetted job postings.

**Live URL**: https://realjobsrealpeople.net
**Deployed on**: Render
**Repository**: https://github.com/mfish324/Job-Board

## Tech Stack

- **Backend**: Django 5.2.6
- **Database**: PostgreSQL (production), SQLite (development)
- **Frontend**: Bootstrap 5, vanilla JavaScript
- **File Storage**: Cloudinary (production), local filesystem (development)
- **Static Files**: WhiteNoise
- **Authentication**: Django auth + django-allauth (Google OAuth)
- **Bot Protection**: Cloudflare Turnstile
- **SMS**: Twilio
- **AI Chatbot**: Anthropic Claude API

## Project Structure

```
RJRP/
├── jobboard/               # Django project settings
│   ├── settings.py         # Main settings (uses python-decouple)
│   ├── urls.py             # Root URL configuration
│   └── wsgi.py
├── jobs/                   # Main application
│   ├── models.py           # User profiles, jobs, applications, scraped listings
│   ├── views.py            # All view functions
│   ├── forms.py            # Django forms with validation
│   ├── urls.py             # App URL patterns
│   ├── utils.py            # Helper functions (SMS, email, Turnstile)
│   ├── unified.py          # UnifiedListing wrapper (merges Job + ScrapedJobListing)
│   ├── middleware.py       # Traffic notification middleware
│   ├── admin.py            # Django admin customizations
│   ├── templatetags/       # Custom template tags
│   │   └── has_tags.py     # HAS pip count filter
│   ├── scoring/            # Hiring Activity Score engine
│   │   ├── config.py       # Score weights, thresholds, band definitions
│   │   ├── engine.py       # Main scoring orchestrator
│   │   └── signals.py      # 13+ individual signal calculators
│   ├── management/commands/ # Custom management commands
│   ├── templates/jobs/     # HTML templates
│   │   ├── base.html       # Base template (ALL CSS is inline here)
│   │   ├── home.html       # Landing page with verified + observed sections
│   │   ├── job_list.html   # Unified browse/filter feed
│   │   ├── job_detail.html # Verified job detail page
│   │   ├── scraped_listing_detail.html  # Observed listing detail
│   │   ├── has_info.html   # HAS algorithm explainer page
│   │   └── partials/       # Reusable includes
│   │       ├── has_pips.html          # Score pip visualization
│   │       └── has_badge_tooltip.html # HAS hover tooltip
│   └── static/jobs/        # CSS, JS, images
├── directory/              # Employer Directory app (deep-link system)
│   ├── models.py          # FeaturedEmployer, JobTitleMapping, DirectoryClick, etc.
│   ├── views.py           # Directory index, employer detail, click-tracking redirect
│   ├── urls.py            # /directory/, /directory/<slug>/, /directory/<slug>/go/
│   ├── utils.py           # Deep-link construction, title matching engine
│   ├── admin.py           # Admin with inlines for categories & overrides
│   ├── management/commands/
│   │   ├── seed_directory.py        # Seed 24 employers, 13 title mappings, overrides
│   │   ├── check_directory_links.py # URL health monitoring for career portals
│   │   └── update_directory_counts.py # Stub for automated count updates
│   └── templates/directory/
│       ├── index.html               # Browse all employers with industry filters
│       ├── employer_detail.html     # Employer page with category pills & claim CTA
│       └── partials/
│           └── spotlight_card.html  # Inline card injected into search results
├── templates/              # Project-level templates
├── media/                  # User uploads (dev only)
├── staticfiles/            # Collected static files
└── requirements.txt        # Python dependencies
```

## Key Models

- **UserProfile**: Extended user model with user_type (job_seeker, employer, recruiter)
- **Job**: Verified job postings with status, salary, location, job_type, experience_level, remote_status, expiration
- **ScrapedJobListing**: Market-observed listings ingested from ATS systems (GenZJobs)
- **HiringActivityScore**: OneToOne to ScrapedJobListing — stores 0-100 score + band
- **Company** / **CompanyHiringProfile**: Company data and hiring behavior tracking
- **JobApplication**: Applications linking users to jobs
- **SavedJob**: Bookmarked jobs for job seekers
- **ListingFeedback**: User feedback on observed listings
- **GenzjobsListing**: Unmanaged model (reads from shared GenZJobs DB)
- **FeaturedEmployer**: Curated directory of major employers with career portal URLs & deep-link patterns
- **JobTitleMapping**: Canonical title → search alias mapping (e.g., "DevOps" ↔ "sre", "platform engineer")
- **DirectoryEmployerCategory**: Maps employers to job categories with per-employer search terms
- **EmployerTitleOverride**: Per-employer role naming overrides (e.g., Google calls DevOps "SRE")
- **DirectoryClick**: Click-through analytics for directory deep-links
- **PhoneVerification**: SMS verification codes
- **EmailVerification**: Email verification tokens
- **TwoFactorCode**: 2FA codes for login security

## User Types

1. **Job Seeker**: Can apply to jobs, upload resumes, opt-in to recruiter contact
2. **Employer**: Can post jobs (requires verification), view applicants, manage company profile
3. **Recruiter**: Can search candidates who opted in, requires verification

## Job Fields

- **job_type**: full_time, part_time, contract, temporary, internship, freelance
- **experience_level**: entry, mid, senior, lead, executive
- **remote_status**: on_site, remote, hybrid
- **expires_at**: Auto-set to 60 days from creation, can be refreshed by employer

## Environment Variables

Required in `.env` (local) or Render dashboard (production):

```
# Core Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=realjobsrealpeople.net,localhost

# Database (Render provides DATABASE_URL)
DATABASE_URL=postgres://...

# Cloudinary (media storage)
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=

# Email (Hostinger SMTP)
EMAIL_HOST=smtp.hostinger.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=notifications@realjobsrealpeople.net

# Twilio (SMS)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Cloudflare Turnstile (bot protection)
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Anthropic (AI chatbot)
ANTHROPIC_API_KEY=

# Optional
TWO_FACTOR_AUTH_ENABLED=True
TRAFFIC_NOTIFICATION_ENABLED=False
ADMIN_NOTIFICATION_EMAIL=
```

## Common Commands

```bash
# Development
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic

# Testing
python manage.py test jobs
python manage.py test directory

# Shell
python manage.py shell
```

## Security Features

- **Rate Limiting**: django-ratelimit on login, signup, contact forms
- **Bot Protection**: Cloudflare Turnstile CAPTCHA
- **2FA**: SMS-based two-factor authentication for users with verified phones
- **XSS Prevention**: bleach library for sanitizing user content
- **CSRF Protection**: Django's built-in CSRF middleware
- **Secure Cookies**: SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE in production
- **HSTS**: Enabled in production

## Recent Features

- Google OAuth login (django-allauth)
- Bulk job upload for employers/admins
- AI-powered job search chatbot
- Traffic notifications to admin
- Two-factor authentication
- Recruiter opt-in system for job seekers
- Job expiration system (60-day default, refresh capability)
- Employer verification required before posting jobs
- Job type, experience level, and remote status filters
- Duplicate job detection with confirmation flow
- Verification badges on job listings (basic/enhanced/complete levels)
- **GenZJobs ATS integration** — ingests market-observed listings from GenZJobs shared database
- **Hiring Activity Score (HAS)** — 0-100 scoring algorithm with 13+ signals (freshness, specificity, company velocity, repost penalty, etc.); publish threshold 65+
- **Trust UI Kit** — announcement bar, verified/observed banners, HAS badge tooltips, first-visit modal, pip score visualization
- **Two listing types**: Verified (employer-posted Job model) and Market-Observed (ScrapedJobListing from ATS ingestion)
- **UnifiedListing** wrapper (`jobs/unified.py`) normalizes both models for templates; verified always sort above observed
- **Earth-tone design system** — terracotta (#C4714F), warm sage (#7A8C6E), gold/amber (#C49A3C), cream (#FAF7F2) palette; Lora headings + DM Sans body
- **Employer Directory** — curated directory of 24 major employers (Google, Goldman Sachs, etc.) with deep-link system to their career portals
- **Deep-link engine** — constructs URLs with search terms prefilled using per-employer URL patterns and title overrides
- **Directory sidebar in search** — when a search matches a job category, a sticky sidebar shows major employers hiring for that role with deep-links to their career portals
- **Title synonym mapping** — 13 canonical categories with broad search aliases (single words like "analyst", "engineer", "sales" match)
- **Directory click tracking** — analytics on employer click-throughs for conversion targeting
- **URL health monitoring** — `check_directory_links` command validates career portal URLs, tracks consecutive failures, auto-marks unhealthy employers
- **Workday fallback URLs** — Workday-sourced listings use search-based fallback URLs instead of stale direct links (Workday URLs are session-based and expire quickly)

## Management Commands

```bash
# Expire stale job listings (run via cron daily)
python manage.py expire_stale_jobs
python manage.py expire_stale_jobs --dry-run  # Preview without changes

# Employer Directory
python manage.py seed_directory              # Seed/update 24 employers, 13 title mappings, overrides
python manage.py check_directory_links       # Check career portal URL health
python manage.py check_directory_links --dry-run
python manage.py check_directory_links --employer google
python manage.py update_directory_counts     # Stub for future automated count updates
python manage.py update_directory_counts --dry-run
python manage.py update_directory_counts --employer google
```

## Deployment Notes

- Render auto-deploys from `main` branch
- ATS feature branch: `ATS-implementation` (deploy this branch on Render for testing)
- Run `python manage.py migrate` after adding new migrations
- Static files served via WhiteNoise
- Media files stored in Cloudinary
- Environment variables set in Render dashboard
- Start command: `gunicorn jobboard.wsgi:application` (check Render dashboard if deploy fails with "No module named 'app'")

## Admin Access

- URL: `/admin/`
- Configure Site domain in Django admin for allauth
- Social Applications configured for Google OAuth

## Important Files to Know

- [jobboard/settings.py](jobboard/settings.py) - All configuration
- [jobs/views.py](jobs/views.py) - Main view logic
- [jobs/models.py](jobs/models.py) - Database models
- [jobs/forms.py](jobs/forms.py) - Form definitions and validation
- [jobs/utils.py](jobs/utils.py) - SMS, email, Turnstile helpers
- [jobs/templates/jobs/base.html](jobs/templates/jobs/base.html) - Base template (all CSS lives here inline)
- [jobs/unified.py](jobs/unified.py) - UnifiedListing wrapper for merging Job + ScrapedJobListing
- [jobs/scoring/](jobs/scoring/) - HAS scoring engine (config.py, engine.py, signals.py)
- [jobs/templates/jobs/partials/](jobs/templates/jobs/partials/) - Reusable template partials (has_pips, has_badge_tooltip)
- [directory/models.py](directory/models.py) - Employer directory models
- [directory/utils.py](directory/utils.py) - Deep-link construction & title matching
- [directory/management/commands/seed_directory.py](directory/management/commands/seed_directory.py) - Directory seed data

## ATS / Market-Observed Architecture

- **ScrapedJobListing** model stores observed listings; **HiringActivityScore** (OneToOne) stores scoring
- Score bands: very_active (80-100), likely_active (65-79), uncertain (50-64), low_signal (0-49)
- Only listings scoring 65+ are published to the board (`published_to_board=True`)
- `{% ifchanged item.is_verified %}` used in job_list.html for section header transitions (not `{% with %}` — Django scoping limitation)
- Branch `ATS-implementation` contains all ATS/HAS/Trust UI work before merging to main

## Employer Directory Architecture

- Separate `directory` Django app with its own models, views, templates, and tests
- **Three content tiers** in search results: Verified (gold), Market-Observed (sage), Directory sidebar (purple)
- Deep-link URL construction: employer URL pattern → title override lookup → category search term → raw query fallback
- Title matching: substring match against alias lists, longest match wins for specificity
- **Directory sidebar**: sticky `col-lg-4` panel appears alongside search results when query matches a canonical title; shows up to 6 employers with deep-links; layout shifts to 8/4 columns (full-width when no match)
- Click-through tracking via `/directory/<slug>/go/` redirect endpoint with source attribution (`search_sidebar`, `directory_page`, `employer_detail`)
- Directory browse at `/directory/` with client-side industry filter chips
- Employer detail at `/directory/<slug>/` with category pills, deep-link CTA, and claim banner
- Seed data: 24 employers, 13 canonical title mappings, 110 category assignments, 5 title overrides
- `seed_directory` is idempotent (uses `update_or_create`)
- **URL health monitoring**: `FeaturedEmployer` has `link_healthy`, `link_last_checked`, `link_status_code`, `link_consecutive_failures` fields; `check_directory_links` command checks base URL + sample deep-link; classifies as healthy/degraded/down/inconclusive (bot-blocked SPAs)
- **Workday fallback**: `build_workday_fallback_url()` in `jobs/utils.py` constructs search URLs from Workday `source_url` domains; primary CTA for Workday-sourced listings uses fallback; direct link shown as secondary option

## Design System — Earth Tone Palette

All CSS lives inline in `base.html`. No external stylesheets or SCSS.

**Brand Colors (CSS vars in `:root`):**
- `--primary-color: #7e512f` — Dark brown (buttons, CTA — do NOT change)
- `--secondary-color: #dda56c` — Tan/gold accent
- `--light-bg: #f5f0e5` — Cream page background

**Earth Tone Tokens:**
- `--verified: #c49a3c` / `--verified-bg: #fdf8ee` — Gold/amber for verified badges & borders
- `--observed: #7a8c6e` / `--observed-bg: #e8ede4` — Warm sage for observed badges & borders
- `--directory-color: #7c3aed` / `--directory-bg: #f5f3ff` — Purple for directory cards & badges
- `--terracotta: #c4714f` — Job type badges (`.badge-job-type`)
- `--card: #faf7f2` — Soft cream card backgrounds
- `--ink: #2c2418` — Dark brown-black for text

**Fonts (Google Fonts):**
- **Lora** (serif) — Job titles only (`.job-title` class)
- **DM Sans** — Body text, UI elements
- **Fraunces** — Section headings, modal titles

**Key CSS Classes:**
- `.job-card-verified` / `.job-card-observed` — Card left-border accent
- `.trust-badge-verified` / `.trust-badge-observed` — Status pills
- `.badge-job-type` (terracotta), `.badge-location`, `.badge-remote`, `.badge-experience` — Tag badges
- `.salary-display` — Green salary line below company
- `.activity-label` — "Active X/100" human-readable score
- `.btn-more-filters` / `.more-filters-row` — Collapsible filter row
- `.directory-card` / `.directory-spotlight-card` — Directory employer cards
- `.directory-sidebar-employer` — Sidebar employer row (hover: purple border + lift)
- `.directory-btn-primary` — Purple CTA buttons for directory
- `.directory-category-pill` — Clickable category pills on employer detail
- `.directory-chip` / `.directory-chip.active` — Industry filter chips on directory index
- `.directory-logo-placeholder` / `.directory-logo-placeholder-sm` — Letter-initial logo fallbacks
- Job card hover: `translateY(-3px)` + `box-shadow: 0 8px 24px rgba(0,0,0,0.1)`

## Setup Checklist for New Features

1. Add any new dependencies to `requirements.txt`
2. Add environment variables to both `.env` and Render
3. Run migrations locally and on Render
4. Test locally before pushing
5. Monitor Render logs after deployment
