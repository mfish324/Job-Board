"""
Generate LinkedIn content drafts from a DailyGhostReport.

Ranks the most interesting findings in the day's report, assembles a data
summary (today's numbers + yesterday's for comparison), and asks Claude to
write 2 post options. Saves them as SocialContentDraft rows (status='draft')
for manual review/approval in admin — nothing is auto-posted.

Usage:
    python manage.py generate_social_content                  # today
    python manage.py generate_social_content --date 2026-05-28
    python manage.py generate_social_content --dry-run        # print, save nothing

# Recommended crontab (after generate_daily_report): 0 10 * * * python manage.py generate_social_content
"""

import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count, Q
from django.utils import timezone

from jobs.models import DailyGhostReport, ScrapedJobListing, SocialContentDraft
from jobs.management.commands.generate_daily_report import UNTAGGED_KEY

MODEL = 'claude-sonnet-4-6'

# Human-readable label for the UNTAGGED segment so Claude never echoes the raw
# sentinel "UNTAGGED" as if it were an industry name.
UNTAGGED_LABEL = 'listings from unidentifiable / unverified employers'

# An "industry" backed by too few distinct employers isn't a market trend — it's
# one or two companies. AEROSPACE_AND_DEFENSE, for example, is ~90% Anduril +
# Palantir, and a single high-volume employer posting its whole board inflates
# the industry's metrics. Exclude such industries from content so we never
# publish a headline like "0% low-activity in aerospace" that's really "Anduril
# posts a lot of fresh listings."
MIN_DISTINCT_COMPANIES = 3

SYSTEM_PROMPT = (
    "You are a LinkedIn content writer for RJRP (Real Jobs, Real People), a job "
    "board that scores listings for hiring activity signals. Write data-driven "
    "posts about job market quality. Tone: conversational, confident, slightly "
    "provocative but never preachy. You are speaking to job seekers in tech."
)

POST_INSTRUCTIONS = """Write 2 LinkedIn post options. Requirements:
- LEAD with finding #1 in the ranked "Most newsworthy findings" list below — it is
  the designated headline (usually the named-vs-unidentifiable employer contrast).
  Do NOT open with a day-over-day "overnight"/"since yesterday" swing even if one
  looks flashier; use lower-ranked findings only as supporting color in the body.
- Keep each post under 200 words
- Reference "Hiring Activity Score" by name at least once
- End with a subtle mention of the tool (e.g., "We built a scoring system that catches this" or "This is what our algorithm flagged today") — not a hard sell
- Maximum 2-3 hashtags, placed at the end
- Do NOT use the phrase "ghost job" in the post — use "hiring activity signals" or "low-activity listings" instead
- Format each post clearly labeled as Option A and Option B"""


class Command(BaseCommand):
    help = 'Generate LinkedIn draft posts from a DailyGhostReport via the Claude API'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='Report date YYYY-MM-DD (default: today)')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print the generated drafts instead of saving them.',
        )
        parser.add_argument(
            '--no-deltas',
            action='store_true',
            help='Ignore day-over-day swing findings (ghost_rate_swing, '
                 'threshold_crossings, company_mover). Use after a scoring change: '
                 "yesterday's scores were computed under the old logic, so deltas "
                 'are migration artifacts, not real market moves.',
        )

    def handle(self, *args, **options):
        report_date = self._resolve_date(options.get('date'))
        dry_run = options['dry_run']
        no_deltas = options['no_deltas']

        reports = list(DailyGhostReport.objects.filter(date=report_date))
        if not reports:
            raise CommandError(
                f'No DailyGhostReport rows for {report_date}. '
                f'Run generate_daily_report first.'
            )

        # Guardrail: drop industries backed by fewer than MIN_DISTINCT_COMPANIES
        # employers — their metrics reflect one or two firms, not a market trend.
        reports = self._filter_single_employer_industries(reports)
        if not reports:
            self.stdout.write(self.style.WARNING(
                f'No industries with >= {MIN_DISTINCT_COMPANIES} distinct employers '
                f'for {report_date}; skipping content generation.'
            ))
            return

        findings = self._rank_findings(reports, no_deltas=no_deltas)
        if not findings:
            self.stdout.write(self.style.WARNING(
                f'No noteworthy findings for {report_date}; skipping content generation.'
            ))
            return

        data_summary = self._assemble_summary(report_date, reports, findings, no_deltas=no_deltas)

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            raise CommandError('ANTHROPIC_API_KEY is not configured.')

        draft_text = self._call_claude(api_key, data_summary)
        if not draft_text:
            raise CommandError('Claude API returned no content.')

        source_metrics = {
            'date': str(report_date),
            'findings': findings,
            'data_summary': data_summary,
            'model': MODEL,
        }

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY RUN] Drafts for {report_date}:\n'))
            self.stdout.write(draft_text)
            self.stdout.write(self.style.WARNING('\n[DRY RUN] Nothing saved.'))
            return

        # Persist the two options. We store the full generated text on each row so
        # the reviewer sees both labeled options; status defaults to 'draft'.
        SocialContentDraft.objects.create(
            date=report_date,
            platform='linkedin',
            draft_text=draft_text,
            source_metrics=source_metrics,
            status='draft',
        )
        self.stdout.write(self.style.SUCCESS(
            f'Created draft post(s) for {report_date}. '
            f'Review in admin or run with --dry-run to preview.'
        ))

    # ------------------------------------------------------------------ #
    # Guardrails
    # ------------------------------------------------------------------ #

    def _filter_single_employer_industries(self, reports):
        """
        Return only the report rows whose industry is backed by at least
        MIN_DISTINCT_COMPANIES distinct employers among active/published
        listings. Logs which industries were excluded (no silent dropping).
        """
        industries = [r.industry_category for r in reports]
        company_counts = {
            row['industry_category']: row['n_companies']
            for row in (
                ScrapedJobListing.objects
                .filter(status__in=['active', 'published'], industry_category__in=industries)
                .values('industry_category')
                .annotate(n_companies=Count('company_name', distinct=True))
            )
        }

        kept, dropped = [], []
        for r in reports:
            n = company_counts.get(r.industry_category, 0)
            if n >= MIN_DISTINCT_COMPANIES:
                kept.append(r)
            else:
                dropped.append((r.industry_category, n))

        for industry, n in dropped:
            self.stdout.write(self.style.WARNING(
                f'  Excluding {industry}: only {n} distinct employer(s) '
                f'(< {MIN_DISTINCT_COMPANIES}) — not a market trend.'
            ))

        return kept

    # ------------------------------------------------------------------ #
    # Finding selection
    # ------------------------------------------------------------------ #

    def _label(self, industry):
        """Render an industry key for human-facing copy (UNTAGGED -> readable)."""
        return UNTAGGED_LABEL if industry == UNTAGGED_KEY else industry

    def _rank_findings(self, reports, no_deltas=False):
        """
        Score each report row across several "interesting" dimensions and return
        the 2-3 most newsworthy findings as plain dicts.

        no_deltas suppresses day-over-day findings (used right after a scoring
        change, when yesterday's numbers were produced under different logic and
        the "swing" is a migration artifact, not a real market move).
        """
        findings = []

        # --- Top-priority cross-segment finding: tagged (named employers) vs
        # UNTAGGED (unidentifiable employers). This is the real, differentiated
        # story — ghost signals concentrate where you can't identify who's hiring.
        findings.extend(self._contrast_finding(reports))

        for r in reports:
            ind = r.industry_category
            label = self._label(ind)

            # Biggest day-over-day ghost rate swing (skipped under --no-deltas)
            if not no_deltas and r.previous_ghost_rate is not None:
                delta = float(r.ghost_rate) - float(r.previous_ghost_rate)
                if abs(delta) >= 2:
                    findings.append({
                        'kind': 'ghost_rate_swing',
                        'industry': ind,
                        'magnitude': abs(delta),
                        'detail': f'{label} low-activity rate moved {delta:+.1f}pts '
                                  f'({r.previous_ghost_rate}% -> {r.ghost_rate}%)',
                    })

            # High absolute ghost rate
            if float(r.ghost_rate) >= 25:
                findings.append({
                    'kind': 'high_ghost_rate',
                    'industry': ind,
                    'magnitude': float(r.ghost_rate),
                    'detail': f'{float(r.ghost_rate):.1f}% of {label} are '
                              f'low-activity (below the 65 Hiring Activity Score threshold)',
                })

            # Low salary transparency
            if float(r.salary_transparency_rate) <= 40:
                findings.append({
                    'kind': 'low_salary_transparency',
                    'industry': ind,
                    'magnitude': 100 - float(r.salary_transparency_rate),
                    'detail': f'Only {float(r.salary_transparency_rate):.0f}% of {label} '
                              f'disclose salary',
                })

            # Spike in threshold crossings (skipped under --no-deltas)
            if not no_deltas and r.threshold_crossings_down >= 5:
                findings.append({
                    'kind': 'threshold_crossings',
                    'industry': ind,
                    'magnitude': r.threshold_crossings_down,
                    'detail': f'{r.threshold_crossings_down} {label} dropped below '
                              f'the activity threshold since yesterday',
                })

            # New listings already looking low-activity
            if r.new_listings_avg_has is not None and float(r.new_listings_avg_has) < 60 \
                    and r.new_listings_today >= 5:
                findings.append({
                    'kind': 'weak_new_listings',
                    'industry': ind,
                    'magnitude': 60 - float(r.new_listings_avg_has),
                    'detail': f"{label}: {r.new_listings_today} new listings today average "
                              f"only {float(r.new_listings_avg_has):.0f} Hiring Activity Score",
                })

            # Dramatic company-level mover (skipped under --no-deltas)
            if not no_deltas:
                down = (r.top_movers or {}).get('down', [])
                if down:
                    worst = down[0]
                    if abs(worst.get('delta', 0)) >= 5:
                        findings.append({
                            'kind': 'company_mover',
                            'industry': ind,
                            'magnitude': abs(worst['delta']),
                            'detail': f"{worst['company']}'s average Hiring Activity Score "
                                      f"fell {worst['delta']} points ({label})",
                        })

        # Rank by magnitude, keep the top 3 — but the contrast finding (if present)
        # is the headline, so pin it first.
        contrast = [f for f in findings if f['kind'] == 'tagged_vs_untagged']
        rest = [f for f in findings if f['kind'] != 'tagged_vs_untagged']
        rest.sort(key=lambda f: f['magnitude'], reverse=True)
        ordered = contrast + rest
        return ordered[:3]

    def _contrast_finding(self, reports):
        """
        Build the tagged-vs-untagged contrast finding: ghost rate among named/
        identifiable employers vs the UNTAGGED long tail. Returns [] if either
        side is missing (e.g. no untagged row in an older report).
        """
        by_key = {r.industry_category: r for r in reports}
        untagged = by_key.get(UNTAGGED_KEY)
        tagged = [r for r in reports if r.industry_category != UNTAGGED_KEY]
        if untagged is None or not tagged:
            return []

        # Volume-weighted ghost rate across tagged industries.
        t_total = sum(r.total_listings for r in tagged)
        if t_total == 0:
            return []
        t_ghost = sum(float(r.ghost_rate) * r.total_listings for r in tagged) / t_total
        u_ghost = float(untagged.ghost_rate)

        return [{
            'kind': 'tagged_vs_untagged',
            'industry': None,
            'magnitude': abs(u_ghost - t_ghost),
            'detail': (
                f'Among NAMED/identifiable employers, only {t_ghost:.0f}% of listings '
                f'show low hiring-activity signals — but among '
                f'{untagged.total_listings:,} listings from unidentifiable/unverified '
                f'employers, {u_ghost:.0f}% do. Who is behind the listing is the '
                f'single biggest predictor of whether it looks real.'
            ),
        }]

    def _assemble_summary(self, report_date, reports, findings, no_deltas=False):
        """Human-readable data block fed to Claude, including yesterday's comparison."""
        lines = [f"Hiring activity data for {report_date}:", ""]
        if no_deltas:
            lines.append(
                "NOTE: Do NOT write about day-over-day changes or 'overnight' moves "
                "today — yesterday's figures used an earlier scoring method, so any "
                "swing is a methodology change, not a market shift. Focus on today's "
                "absolute numbers and the named-vs-unidentifiable contrast.")
            lines.append("")
        for r in reports:
            label = 'Unidentifiable/unverified employers' if r.industry_category == UNTAGGED_KEY else r.industry_category
            lines.append(f"Segment: {label}")
            lines.append(f"  Total active listings: {r.total_listings}")
            lines.append(f"  Low-activity rate (below 65): {float(r.ghost_rate):.1f}%")
            if r.previous_ghost_rate is not None and not no_deltas:
                lines.append(f"  Yesterday's low-activity rate: {float(r.previous_ghost_rate):.1f}%")
            lines.append(f"  Average Hiring Activity Score: {float(r.avg_has):.1f}")
            lines.append(f"  Median Hiring Activity Score: {float(r.median_has):.1f}")
            lines.append(f"  Salary disclosed: {float(r.salary_transparency_rate):.0f}%")
            lines.append(f"  Listings reposted 3+ times: {float(r.repost_rate):.0f}%")
            lines.append(f"  Open 90+ days unchanged: {float(r.evergreen_rate):.0f}%")
            lines.append(f"  New listings today: {r.new_listings_today}"
                         + (f" (avg HAS {float(r.new_listings_avg_has):.0f})"
                            if r.new_listings_avg_has is not None else ""))
            if not no_deltas:
                lines.append(f"  Dropped below threshold since yesterday: {r.threshold_crossings_down}")
            lines.append("")

        lines.append("Most newsworthy findings (ranked):")
        for i, f in enumerate(findings, 1):
            lines.append(f"  {i}. {f['detail']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Claude call
    # ------------------------------------------------------------------ #

    def _call_claude(self, api_key, data_summary):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
            response = client.messages.create(
                model=MODEL,
                max_tokens=1200,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": (
                        f"Here is today's hiring activity data:\n\n{data_summary}\n\n"
                        f"{POST_INSTRUCTIONS}"
                    ),
                }],
            )
            return response.content[0].text.strip()
        except Exception as e:
            raise CommandError(f'Claude API call failed: {e}')

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def _resolve_date(self, date_str):
        if not date_str:
            return timezone.localdate()
        try:
            return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f'Invalid --date {date_str!r}; expected YYYY-MM-DD')
