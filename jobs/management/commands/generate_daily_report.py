"""
Generate the Daily Ghost Job Report — aggregated HAS metrics per industry.

For each industry (ScrapedJobListing.industry_category), aggregates the
ALREADY-STORED Hiring Activity Scores into one DailyGhostReport row, and writes
a per-listing DailyScoreSnapshot so day-over-day deltas (threshold crossings,
per-company movers) can be computed on subsequent runs.

This command NEVER recomputes HAS scores — it reads listing.activity_score.
Run it AFTER the daily rescore so scores are fresh.

Usage:
    python manage.py generate_daily_report                 # today
    python manage.py generate_daily_report --date 2026-05-28
    python manage.py generate_daily_report --dry-run       # compute + print, save nothing

# Recommended crontab (after the 09:00 UTC rescore): 30 9 * * * python manage.py generate_daily_report
"""

import datetime
import statistics
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from jobs.models import (
    ScrapedJobListing,
    DailyGhostReport,
    DailyScoreSnapshot,
)
from jobs.scoring.config import get_config

SNAPSHOT_RETENTION_DAYS = 35

# Sentinel "industry" for listings with no industry_category. These are the
# unidentifiable/long-tail companies where ghost-job signals concentrate (~90%
# below threshold vs ~5% for tagged big-name employers). Stored as a normal
# DailyGhostReport row so the report surfaces the real ghost story, not just the
# clean tagged industries. Kept out of single-employer-style content guardrails
# by being explicitly labelled.
UNTAGGED_KEY = 'UNTAGGED'

# The report covers only listings POSTED within this window (by real posting
# date: date_posted_external, falling back to date_first_seen). All-time
# aggregates were dominated by the ~64% March bulk-import cohort, which is now
# 90+ days old and scores low purely on age — making every ghost rate a
# staleness artifact (untagged read 90%, mostly old). A 30-day window measures
# CURRENT hiring activity: untagged drops to a believable ~26%, and the
# tagged-vs-untagged contrast stays honest. Tunable via --recent-days.
DEFAULT_RECENT_DAYS = 30


class Command(BaseCommand):
    help = 'Aggregate stored HAS scores into per-industry DailyGhostReport rows'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Report date YYYY-MM-DD (default: today). Allows backfill/rerun.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Compute and print the report without writing snapshots or report rows.',
        )
        parser.add_argument(
            '--recent-days',
            type=int,
            default=DEFAULT_RECENT_DAYS,
            help=f'Only include listings posted within this many days, by real '
                 f'posting date (default: {DEFAULT_RECENT_DAYS}). Set 0 for all-time '
                 f'(not recommended — old bulk-import cohort skews ghost rates).',
        )

    def handle(self, *args, **options):
        config = get_config()
        self.threshold = config['publish_threshold']  # 65

        report_date = self._resolve_date(options.get('date'))
        dry_run = options['dry_run']
        recent_days = options['recent_days']

        now = timezone.now()
        new_cutoff = now - datetime.timedelta(hours=24)

        # All active, scored listings — both industry-tagged AND untagged. The
        # untagged long tail (unidentifiable companies) is where the ghost-job
        # signal concentrates, so it gets its own aggregate row (UNTAGGED_KEY).
        # We read the score from the related HiringActivityScore (no recompute).
        listings = (
            ScrapedJobListing.objects
            .filter(Q(status='active') | Q(status='published'))
            .filter(activity_score__isnull=False)
            .select_related('activity_score')
            .only(
                'id', 'company_name', 'industry_category', 'repost_count',
                'salary_min', 'salary_max', 'date_first_seen', 'date_posted_external',
                'activity_score__total_score',
            )
        )

        # Recency filter: only listings POSTED within recent_days, by real posting
        # date. Mirrors the scoring clamp (days_since_posted): use
        # date_posted_external when it's sane (>= 2025), else date_first_seen.
        # Done at the DB layer so we don't pull the whole stale corpus into memory.
        if recent_days and recent_days > 0:
            cutoff = now - datetime.timedelta(days=recent_days)
            ext_floor = timezone.make_aware(datetime.datetime(2025, 1, 1)) \
                if timezone.is_aware(now) else datetime.datetime(2025, 1, 1)
            listings = listings.filter(
                # external date is sane AND within window …
                Q(date_posted_external__gte=cutoff)
                # … or external date is missing/garbage, so fall back to first_seen
                | (
                    (Q(date_posted_external__isnull=True) | Q(date_posted_external__lt=ext_floor))
                    & Q(date_first_seen__gte=cutoff)
                )
            )

        # Bucket listings by industry (untagged -> UNTAGGED_KEY), collecting only
        # the lightweight fields we need.
        # rows[industry] = list of per-listing dicts (ints/dates only — tiny memory).
        rows = defaultdict(list)

        for lst in listings.iterator(chunk_size=500):
            score = lst.activity_score.total_score
            age_days = (now - lst.date_first_seen).days if lst.date_first_seen else 0
            industry = lst.industry_category or ''
            industry = industry.strip() or UNTAGGED_KEY
            rows[industry].append({
                'listing_id': lst.id,
                'company_name': lst.company_name or '',
                'score': score,
                'repost_count': lst.repost_count or 0,
                'has_salary': bool(lst.salary_min or lst.salary_max),
                'age_days': age_days,
                'is_new': bool(lst.date_first_seen and lst.date_first_seen >= new_cutoff),
            })

        if not rows:
            window = f'posted in last {recent_days}d' if recent_days else 'all-time'
            self.stdout.write(self.style.WARNING(
                f'No scored active listings found ({window}). Nothing to report.'
            ))
            return

        # Load prior-day data once for deltas.
        prev_date = report_date - datetime.timedelta(days=1)
        prev_reports = {
            r.industry_category: r
            for r in DailyGhostReport.objects.filter(date=prev_date)
        }
        # Prior snapshots, loaded once for the prior date:
        #   prev_scores[industry]   = {listing_id: score}     (for threshold crossings)
        #   prev_co_scores[industry] = {company: [scores...]}  (for top_movers)
        prev_scores = defaultdict(dict)
        prev_co_scores = defaultdict(lambda: defaultdict(list))
        for snap in DailyScoreSnapshot.objects.filter(date=prev_date).iterator(chunk_size=1000):
            prev_scores[snap.industry_category][snap.listing_id] = snap.total_score
            prev_co_scores[snap.industry_category][snap.company_name].append(snap.total_score)

        # --- Write today's snapshots (unless dry-run) ---
        if not dry_run:
            self._write_snapshots(report_date, rows)
            self._prune_snapshots(report_date)

        # --- Build a report row per industry ---
        # Real industries alphabetically, UNTAGGED last so it reads as its own
        # segment in the summary.
        ordered = sorted(rows.items(), key=lambda kv: (kv[0] == UNTAGGED_KEY, kv[0]))
        results = []
        for industry, items in ordered:
            metrics = self._compute_metrics(industry, items)
            metrics.update(self._compute_deltas(
                industry, items,
                prev_report=prev_reports.get(industry),
                prev_scores=prev_scores.get(industry, {}),
                prev_co_scores=prev_co_scores.get(industry, {}),
            ))
            results.append((industry, metrics))

            if not dry_run:
                DailyGhostReport.objects.update_or_create(
                    date=report_date,
                    industry_category=industry,
                    defaults=metrics,
                )

        self._print_summary(report_date, results, dry_run, recent_days)

    # ------------------------------------------------------------------ #
    # Metric computation
    # ------------------------------------------------------------------ #

    def _compute_metrics(self, industry, items):
        """Single-day metrics from the bucketed listing dicts for one industry."""
        total = len(items)
        scores = [it['score'] for it in items]

        above = sum(1 for s in scores if s >= self.threshold)
        below = total - above

        new_items = [it for it in items if it['is_new']]
        new_scores = [it['score'] for it in new_items]

        staleness = {'0_14d': 0, '15_30d': 0, '31_60d': 0, '61_90d': 0, '90d_plus': 0}
        evergreen = 0
        for it in items:
            age = it['age_days']
            if age <= 14:
                staleness['0_14d'] += 1
            elif age <= 30:
                staleness['15_30d'] += 1
            elif age <= 60:
                staleness['31_60d'] += 1
            elif age <= 90:
                staleness['61_90d'] += 1
            else:
                staleness['90d_plus'] += 1
            # Evergreen: open 90+ days with no updates (matches HAS evergreen_penalty)
            if age >= 90 and it['repost_count'] == 0:
                evergreen += 1

        salary_present = sum(1 for it in items if it['has_salary'])
        reposters = sum(1 for it in items if it['repost_count'] >= 3)

        return {
            'total_listings': total,
            'above_threshold_count': above,
            'below_threshold_count': below,
            'ghost_rate': self._pct(below, total),
            'avg_has': round(statistics.fmean(scores), 2) if scores else 0,
            'median_has': round(statistics.median(scores), 2) if scores else 0,
            'salary_transparency_rate': self._pct(salary_present, total),
            'repost_rate': self._pct(reposters, total),
            'evergreen_rate': self._pct(evergreen, total),
            'staleness_buckets': staleness,
            'new_listings_today': len(new_items),
            'new_listings_avg_has': (
                round(statistics.fmean(new_scores), 2) if new_scores else None
            ),
        }

    def _compute_deltas(self, industry, items, prev_report, prev_scores, prev_co_scores):
        """Day-over-day metrics requiring yesterday's snapshot / report."""
        # threshold_crossings_down: was >= threshold yesterday, < threshold today
        crossings = 0
        for it in items:
            prev = prev_scores.get(it['listing_id'])
            if prev is not None and prev >= self.threshold and it['score'] < self.threshold:
                crossings += 1

        # top_movers: per-company avg HAS today vs yesterday (companies present both days)
        top_movers = {'up': [], 'down': []}
        if prev_co_scores:
            today_by_co = defaultdict(list)
            for it in items:
                today_by_co[it['company_name']].append(it['score'])

            deltas = []
            for company, scores in today_by_co.items():
                prev_list = prev_co_scores.get(company)
                if prev_list:
                    cur_avg = statistics.fmean(scores)
                    delta = cur_avg - statistics.fmean(prev_list)
                    if abs(delta) >= 0.5:  # ignore noise
                        deltas.append({
                            'company': company,
                            'delta': round(delta, 1),
                            'current_avg': round(cur_avg, 1),
                        })
            deltas.sort(key=lambda d: d['delta'], reverse=True)
            top_movers['up'] = [d for d in deltas if d['delta'] > 0][:5]
            top_movers['down'] = [d for d in deltas if d['delta'] < 0][-5:][::-1]

        return {
            'threshold_crossings_down': crossings,
            'top_movers': top_movers,
            'previous_ghost_rate': prev_report.ghost_rate if prev_report else None,
        }

    # ------------------------------------------------------------------ #
    # Persistence helpers
    # ------------------------------------------------------------------ #

    def _write_snapshots(self, report_date, rows):
        """Idempotently write per-listing snapshots for report_date."""
        # Clear any existing snapshots for this date (rerun safety), then bulk insert.
        DailyScoreSnapshot.objects.filter(date=report_date).delete()
        objs = []
        for industry, items in rows.items():
            for it in items:
                objs.append(DailyScoreSnapshot(
                    date=report_date,
                    listing_id=it['listing_id'],
                    company_name=it['company_name'],
                    industry_category=industry,
                    total_score=it['score'],
                ))
        DailyScoreSnapshot.objects.bulk_create(objs, batch_size=500)

    def _prune_snapshots(self, report_date):
        cutoff = report_date - datetime.timedelta(days=SNAPSHOT_RETENTION_DAYS)
        deleted, _ = DailyScoreSnapshot.objects.filter(date__lt=cutoff).delete()
        if deleted:
            self.stdout.write(f'Pruned {deleted} snapshot row(s) older than {cutoff}.')

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pct(part, whole):
        return round((part / whole) * 100, 2) if whole else 0

    def _resolve_date(self, date_str):
        if not date_str:
            return timezone.localdate()
        try:
            return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            raise CommandError(f'Invalid --date {date_str!r}; expected YYYY-MM-DD')

    def _print_summary(self, report_date, results, dry_run, recent_days=None):
        prefix = '[DRY RUN] ' if dry_run else ''
        window = f' (posted last {recent_days}d)' if recent_days else ' (all-time)'
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Daily Ghost Job Report - {report_date}{window}'
        ))
        line = '-' * 72
        self.stdout.write(line)
        self.stdout.write(
            f'{"Industry":<24}{"Total":>7}{"Ghost":>9}{"DelDay":>9}{"AvgHAS":>9}{"CrossDn":>8}'
        )
        self.stdout.write(line)
        for industry, m in results:
            prev = m['previous_ghost_rate']
            if prev is None:
                delta_str = 'n/a'
            else:
                d = float(m['ghost_rate']) - float(prev)
                delta_str = f'{"+" if d >= 0 else ""}{d:.1f}%'
            self.stdout.write(
                f'{industry[:24]:<24}'
                f'{m["total_listings"]:>7}'
                f'{float(m["ghost_rate"]):>8.1f}%'
                f'{delta_str:>9}'
                f'{float(m["avg_has"]):>9.1f}'
                f'{m["threshold_crossings_down"]:>8}'
            )
        self.stdout.write(line)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                '[DRY RUN] No snapshots or report rows were written.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Wrote {len(results)} report row(s) for {report_date}.'
            ))
