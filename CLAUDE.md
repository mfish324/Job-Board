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

## Management Commands

```bash
# Expire stale job listings (run via cron daily)
python manage.py expire_stale_jobs
python manage.py expire_stale_jobs --dry-run  # Preview without changes
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

## ATS / Market-Observed Architecture

- **ScrapedJobListing** model stores observed listings; **HiringActivityScore** (OneToOne) stores scoring
- Score bands: very_active (80-100), likely_active (65-79), uncertain (50-64), low_signal (0-49)
- Only listings scoring 65+ are published to the board (`published_to_board=True`)
- `{% ifchanged item.is_verified %}` used in job_list.html for section header transitions (not `{% with %}` — Django scoping limitation)
- Branch `ATS-implementation` contains all ATS/HAS/Trust UI work before merging to main

## Design System — Earth Tone Palette

All CSS lives inline in `base.html`. No external stylesheets or SCSS.

**Brand Colors (CSS vars in `:root`):**
- `--primary-color: #7e512f` — Dark brown (buttons, CTA — do NOT change)
- `--secondary-color: #dda56c` — Tan/gold accent
- `--light-bg: #f5f0e5` — Cream page background

**Earth Tone Tokens:**
- `--verified: #c49a3c` / `--verified-bg: #fdf8ee` — Gold/amber for verified badges & borders
- `--observed: #7a8c6e` / `--observed-bg: #e8ede4` — Warm sage for observed badges & borders
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
- Job card hover: `translateY(-3px)` + `box-shadow: 0 8px 24px rgba(0,0,0,0.1)`

## Setup Checklist for New Features

1. Add any new dependencies to `requirements.txt`
2. Add environment variables to both `.env` and Render
3. Run migrations locally and on Render
4. Test locally before pushing
5. Monitor Render logs after deployment
