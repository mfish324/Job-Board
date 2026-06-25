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
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from jobs.models import DailyGhostReport, ScrapedJobListing, SocialContentDraft
from jobs.management.commands.generate_daily_report import UNTAGGED_KEY

MODEL = 'claude-sonnet-4-6'

UNTAGGED_LABEL = 'listings from unidentifiable / unverified employers'
MIN_DISTINCT_COMPANIES = 3

# A salary_transparency_rate of exactly 0% is a data-capture artifact (RJRP doesn't
# parse salary from tagged ATS feeds), not employer behavior. Only surface it as a
# finding when SOME disclosure exists.
SALARY_DISCLOSURE_FLOOR = 0.0

# Week-over-week trend detection.
TREND_TOTAL_CHANGE_MIN = 2.0   # min total ghost-rate change (pts) over the window
TREND_CONSISTENT_DAYS = 4      # min same-direction daily moves out of up to 6
TREND_DAILY_DELTA_MIN = 0.3    # per-day ghost-rate delta (pts) to count as directional

# Volume surge / drop: flag if day-over-day listing count shifts by at least this %.
VOLUME_CHANGE_PCT_MIN = 15.0

# Staleness: flag if >= this % of an industry's listings are open 90+ days unchanged.
EVERGREEN_THRESHOLD = 20.0

SYSTEM_PROMPT = (
    "You are a LinkedIn content writer for RJRP (Real Jobs, Real People), a job "
    "board that scores listings for hiring activity signals. Write data-driven "
    "posts about job market quality. Tone: conversational, confident, slightly "
    "provocative but never preachy. You are speaking to job seekers and hiring "
    "professionals in tech and beyond."
)

POST_INSTRUCTIONS = """Write 2 LinkedIn post options with DISTINCT angles, audiences, and hooks.

Option A — Hot take / provocation for job seekers:
- Open with a specific number as the very first line — no "hey", no preamble, no setup sentence
- Challenge a common assumption about job listings or the hiring process
- Tone: bold, a little edgy, makes someone stop scrolling
- Under 175 words; 2-3 hashtags at the end only

Option B — Data narrative for hiring professionals (recruiters / talent teams / hiring managers):
- Open from a COMPLETELY DIFFERENT angle than Option A — different finding, different frame, different audience
- Tell a short story: observation → insight → implication for their work
- Tone: analytical, credible, slightly surprising
- Under 200 words; 2-3 hashtags at the end only

Requirements for BOTH:
- Incorporate the top finding from "Most newsworthy findings" in at least one post
- Reference "Hiring Activity Score" by name at least once across the two posts combined
- End at least one post with a subtle mention of the tool
  (e.g., "We built a scoring system that flags this", "This is what our algorithm caught today")
- Do NOT use the phrase "ghost job" — use "hiring activity signals" or "low-activity listings"
- Do NOT begin either post with the word "I"
- Label each post clearly as "Option A" and "Option B"
"""


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

        reports = self._filter_single_employer_industries(reports)
        if not reports:
            self.stdout.write(self.style.WARNING(
                f'No industries with >= {MIN_DISTINCT_COMPANIES} distinct employers '
                f'for {report_date}; skipping content generation.'
            ))
            return

        # Load yesterday's reports for volume-change findings.
        prev_date = report_date - datetime.timedelta(days=1)
        prev_reports = {
            r.industry_category: r
            for r in DailyGhostReport.objects.filter(date=prev_date)
        }

        findings = self._rank_findings(
            reports,
            no_deltas=no_deltas,
            report_date=report_date,
            prev_reports=prev_reports,
        )
        if not findings:
            self.stdout.write(self.style.WARNING(
                f'No noteworthy findings for {report_date}; skipping content generation.'
            ))
            return

        recent_angles = self._recent_post_angles(report_date)
        data_summary = self._assemble_summary(report_date, reports, findings, no_deltas=no_deltas)

        api_key = getattr(settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            raise CommandError('ANTHROPIC_API_KEY is not configured.')

        draft_text = self._call_claude(api_key, data_summary, recent_angles)
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
        Return only report rows backed by at least MIN_DISTINCT_COMPANIES employers.
        Always keeps UNTAGGED (it spans thousands of employers by definition); logs
        any excluded industries so nothing is dropped silently.
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
            # UNTAGGED listings store a blank industry_category (not the literal
            # sentinel), so the company count query above returns 0 for UNTAGGED_KEY.
            # Exempt it unconditionally — its pool is inherently multi-employer.
            if r.industry_category == UNTAGGED_KEY:
                kept.append(r)
                continue
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
        return UNTAGGED_LABEL if industry == UNTAGGED_KEY else industry

    def _rank_findings(self, reports, no_deltas=False, report_date=None, prev_reports=None):
        """
        Build a ranked list of the 2-3 most newsworthy findings for the day.

        Finding types (per-industry, UNTAGGED excluded from per-industry checks):
          ghost_rate_swing       — large day-over-day ghost rate move
          high_ghost_rate        — absolute ghost rate >= 25%
          low_salary_transparency — industry hiding salary (floor > 0 guard)
          threshold_crossings    — spike in listings dropping below threshold
          weak_new_listings      — today's new listings arriving with low HAS
          company_mover          — single company's avg HAS fell sharply
          week_trend_up/down     — consistent 5-7 day directional trend
          high_staleness         — high % of listings 90+ days old unchanged
          volume_change          — listing volume surged or dropped overnight
          tagged_vs_untagged     — named vs unidentifiable employer contrast

        Lead rotation: every 3rd calendar day (by date ordinal) the named-vs-
        unidentifiable contrast leads as finding #1. On other days the highest-
        magnitude non-contrast finding leads, and the contrast appears as
        background context in the data summary rather than the headline.
        """
        findings = []

        for r in reports:
            # UNTAGGED is covered exclusively by the contrast finding below.
            if r.industry_category == UNTAGGED_KEY:
                continue

            ind = r.industry_category
            label = self._label(ind)

            if not no_deltas and r.previous_ghost_rate is not None:
                delta = float(r.ghost_rate) - float(r.previous_ghost_rate)
                if abs(delta) >= 2:
                    findings.append({
                        'kind': 'ghost_rate_swing',
                        'industry': ind,
                        'magnitude': abs(delta),
                        'detail': (
                            f'{label} low-activity rate moved {delta:+.1f}pts '
                            f'({r.previous_ghost_rate}% → {r.ghost_rate}%)'
                        ),
                    })

            if float(r.ghost_rate) >= 25:
                findings.append({
                    'kind': 'high_ghost_rate',
                    'industry': ind,
                    'magnitude': float(r.ghost_rate),
                    'detail': (
                        f'{float(r.ghost_rate):.1f}% of {label} are low-activity '
                        f'(below the 65 Hiring Activity Score threshold)'
                    ),
                })

            if SALARY_DISCLOSURE_FLOOR < float(r.salary_transparency_rate) <= 40:
                findings.append({
                    'kind': 'low_salary_transparency',
                    'industry': ind,
                    'magnitude': 100 - float(r.salary_transparency_rate),
                    'detail': (
                        f'Only {float(r.salary_transparency_rate):.0f}% of {label} '
                        f'disclose salary'
                    ),
                })

            if not no_deltas and r.threshold_crossings_down >= 5:
                findings.append({
                    'kind': 'threshold_crossings',
                    'industry': ind,
                    'magnitude': r.threshold_crossings_down,
                    'detail': (
                        f'{r.threshold_crossings_down} {label} listings dropped below '
                        f'the activity threshold since yesterday'
                    ),
                })

            if r.new_listings_avg_has is not None \
                    and float(r.new_listings_avg_has) < 60 \
                    and r.new_listings_today >= 5:
                findings.append({
                    'kind': 'weak_new_listings',
                    'industry': ind,
                    'magnitude': 60 - float(r.new_listings_avg_has),
                    'detail': (
                        f'{label}: {r.new_listings_today} new listings today average '
                        f'only {float(r.new_listings_avg_has):.0f} Hiring Activity Score'
                    ),
                })

            if not no_deltas:
                down = (r.top_movers or {}).get('down', [])
                if down:
                    worst = down[0]
                    if abs(worst.get('delta', 0)) >= 5:
                        findings.append({
                            'kind': 'company_mover',
                            'industry': ind,
                            'magnitude': abs(worst['delta']),
                            'detail': (
                                f"{worst['company']}'s average Hiring Activity Score "
                                f"fell {worst['delta']} points ({label})"
                            ),
                        })

        # New finding types that look across the full history or at structural patterns.
        if report_date:
            findings.extend(self._week_trend_findings(reports, report_date))
        findings.extend(self._staleness_findings(reports))
        if prev_reports:
            findings.extend(self._volume_findings(reports, prev_reports))

        # Rank non-contrast findings by magnitude.
        findings.sort(key=lambda f: f['magnitude'], reverse=True)

        # Lead rotation: every 3rd day by date ordinal the contrast is finding #1;
        # other days the best non-contrast finding leads and contrast is background.
        contrast_findings = self._contrast_finding(reports)
        ordinal = report_date.toordinal() if report_date else 0
        lead_contrast = (ordinal % 3 == 0) and bool(contrast_findings)

        if lead_contrast:
            ordered = contrast_findings + findings
        else:
            # Keep up to 2 non-contrast leads; contrast fills slot 3 as supporting data.
            ordered = findings[:2] + contrast_findings

        return ordered[:3]

    def _contrast_finding(self, reports):
        """
        Named/identifiable employers vs unidentifiable long tail.
        Returns [] if either side is missing from the day's report.
        """
        by_key = {r.industry_category: r for r in reports}
        untagged = by_key.get(UNTAGGED_KEY)
        tagged = [r for r in reports if r.industry_category != UNTAGGED_KEY]
        if untagged is None or not tagged:
            return []

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

    def _week_trend_findings(self, reports, report_date):
        """
        Detect industries with a consistent 5-7 day directional ghost-rate trend.
        Returns at most one finding (the largest-magnitude trend).
        """
        tagged_industries = [
            r.industry_category for r in reports if r.industry_category != UNTAGGED_KEY
        ]
        if not tagged_industries:
            return []

        cutoff = report_date - datetime.timedelta(days=7)
        history_rows = (
            DailyGhostReport.objects
            .filter(
                industry_category__in=tagged_industries,
                date__gte=cutoff,
                date__lte=report_date,
            )
            .values('industry_category', 'date', 'ghost_rate')
            .order_by('industry_category', '-date')
        )

        by_industry = defaultdict(list)
        for row in history_rows:
            by_industry[row['industry_category']].append(float(row['ghost_rate']))

        findings = []
        for industry, rates in by_industry.items():
            if len(rates) < 5:
                continue
            # rates[0] = today (newest), rates[-1] = oldest.
            # delta[i] = rates[i] - rates[i+1]: positive means ghost rate rose that day.
            deltas = [rates[i] - rates[i + 1] for i in range(len(rates) - 1)]
            up_moves = sum(1 for d in deltas if d > TREND_DAILY_DELTA_MIN)
            down_moves = sum(1 for d in deltas if d < -TREND_DAILY_DELTA_MIN)
            total_change = rates[0] - rates[-1]
            label = self._label(industry)

            if up_moves >= TREND_CONSISTENT_DAYS and total_change >= TREND_TOTAL_CHANGE_MIN:
                findings.append({
                    'kind': 'week_trend_up',
                    'industry': industry,
                    'magnitude': abs(total_change),
                    'detail': (
                        f'{label} low-activity rate has risen {total_change:+.1f}pts '
                        f'over the past {len(rates)} days '
                        f'({up_moves} of {len(deltas)} daily moves upward; now {rates[0]:.1f}%)'
                    ),
                })
            elif down_moves >= TREND_CONSISTENT_DAYS and total_change <= -TREND_TOTAL_CHANGE_MIN:
                findings.append({
                    'kind': 'week_trend_down',
                    'industry': industry,
                    'magnitude': abs(total_change),
                    'detail': (
                        f'{label} low-activity rate has fallen {abs(total_change):.1f}pts '
                        f'over the past {len(rates)} days '
                        f'({down_moves} of {len(deltas)} daily moves downward; now {rates[0]:.1f}%)'
                    ),
                })

        findings.sort(key=lambda f: f['magnitude'], reverse=True)
        return findings[:1]

    def _staleness_findings(self, reports):
        """
        Flag industries where a large share of listings are evergreen stale
        (open 90+ days, never reposted). Returns at most one finding.
        """
        findings = []
        for r in reports:
            if r.industry_category == UNTAGGED_KEY:
                continue
            rate = float(r.evergreen_rate)
            if rate >= EVERGREEN_THRESHOLD:
                stale_count = int(r.total_listings * rate / 100)
                label = self._label(r.industry_category)
                findings.append({
                    'kind': 'high_staleness',
                    'industry': r.industry_category,
                    'magnitude': rate,
                    'detail': (
                        f'{rate:.0f}% of {label} listings have been open 90+ days '
                        f'with no updates ({stale_count} of {r.total_listings} listings '
                        f'are stale evergreens)'
                    ),
                })
        findings.sort(key=lambda f: f['magnitude'], reverse=True)
        return findings[:1]

    def _volume_findings(self, reports, prev_reports):
        """
        Flag industries where total active listing count changed significantly
        day-over-day (surge or drop). Returns at most one finding.
        """
        findings = []
        for r in reports:
            if r.industry_category == UNTAGGED_KEY:
                continue
            prev = prev_reports.get(r.industry_category)
            if prev is None or prev.total_listings == 0:
                continue
            pct_change = ((r.total_listings - prev.total_listings) / prev.total_listings) * 100
            if abs(pct_change) < VOLUME_CHANGE_PCT_MIN:
                continue
            label = self._label(r.industry_category)
            direction = 'surged' if pct_change > 0 else 'dropped'
            findings.append({
                'kind': 'volume_change',
                'industry': r.industry_category,
                'magnitude': abs(pct_change),
                'detail': (
                    f'{label} listing volume {direction} {abs(pct_change):.0f}% overnight '
                    f'({prev.total_listings:,} → {r.total_listings:,} active listings)'
                ),
            })
        findings.sort(key=lambda f: f['magnitude'], reverse=True)
        return findings[:1]

    def _recent_post_angles(self, report_date):
        """
        Return a block describing the last 5 LinkedIn draft angles so Claude
        can avoid repeating the same hook or frame two days running.
        """
        recent = list(
            SocialContentDraft.objects
            .filter(date__lt=report_date, platform='linkedin')
            .order_by('-date')[:5]
        )
        if not recent:
            return ''
        lines = ['Recent post angles — do NOT repeat these exact openings, frames, or hooks:']
        for draft in recent:
            metrics = draft.source_metrics or {}
            findings_list = metrics.get('findings', [])
            if findings_list:
                top = findings_list[0]
                kind = top.get('kind', 'unknown')
                detail_snippet = top.get('detail', '')[:120]
                lines.append(f'  {draft.date} [{kind}]: {detail_snippet}')
            else:
                first_line = (draft.draft_text or '').split('\n')[0][:120]
                lines.append(f'  {draft.date}: {first_line}')
        return '\n'.join(lines)

    def _assemble_summary(self, report_date, reports, findings, no_deltas=False):
        """Human-readable data block fed to Claude, including yesterday's comparison."""
        lines = [f'Hiring activity data for {report_date}:', '']
        if no_deltas:
            lines.append(
                'NOTE: Do NOT write about day-over-day changes or "overnight" moves '
                'today — yesterday\'s figures used an earlier scoring method, so any '
                'swing is a methodology change, not a market shift. Focus on today\'s '
                'absolute numbers and the named-vs-unidentifiable contrast.'
            )
            lines.append('')
        for r in reports:
            label = (
                'Unidentifiable/unverified employers'
                if r.industry_category == UNTAGGED_KEY
                else r.industry_category
            )
            lines.append(f'Segment: {label}')
            lines.append(f'  Total active listings: {r.total_listings}')
            lines.append(f'  Low-activity rate (below 65): {float(r.ghost_rate):.1f}%')
            if r.previous_ghost_rate is not None and not no_deltas:
                lines.append(f'  Yesterday\'s low-activity rate: {float(r.previous_ghost_rate):.1f}%')
            lines.append(f'  Average Hiring Activity Score: {float(r.avg_has):.1f}')
            lines.append(f'  Median Hiring Activity Score: {float(r.median_has):.1f}')
            lines.append(f'  Salary disclosed: {float(r.salary_transparency_rate):.0f}%')
            lines.append(f'  Listings reposted 3+ times: {float(r.repost_rate):.0f}%')
            lines.append(f'  Open 90+ days unchanged (evergreen): {float(r.evergreen_rate):.0f}%')
            lines.append(
                f'  New listings today: {r.new_listings_today}'
                + (f' (avg HAS {float(r.new_listings_avg_has):.0f})'
                   if r.new_listings_avg_has is not None else '')
            )
            if not no_deltas:
                lines.append(f'  Dropped below threshold since yesterday: {r.threshold_crossings_down}')
            lines.append('')

        # When the contrast is not finding #1 today (lead rotation), include it as
        # background context so Claude has the numbers even if a different finding leads.
        contrast_findings = self._contrast_finding(reports)
        if contrast_findings and (not findings or findings[0].get('kind') != 'tagged_vs_untagged'):
            lines.append('Background context (always relevant — not today\'s headline):')
            lines.append(f'  {contrast_findings[0]["detail"]}')
            lines.append('')

        lines.append('Most newsworthy findings (ranked — finding #1 is the designated headline):')
        for i, f in enumerate(findings, 1):
            lines.append(f'  {i}. {f["detail"]}')
        return '\n'.join(lines)

    # ------------------------------------------------------------------ #
    # Claude call
    # ------------------------------------------------------------------ #

    def _call_claude(self, api_key, data_summary, recent_angles=''):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
            user_content = f'Here is today\'s hiring activity data:\n\n{data_summary}\n\n'
            if recent_angles:
                user_content += f'{recent_angles}\n\n'
            user_content += POST_INSTRUCTIONS
            response = client.messages.create(
                model=MODEL,
                max_tokens=1200,
                system=SYSTEM_PROMPT,
                messages=[{
                    'role': 'user',
                    'content': user_content,
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
