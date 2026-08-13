"""
Salary extraction from job description text.

Direct-ATS feeds routinely omit structured salary fields even though the
listing text contains a legally-mandated range (CA/NY/CO/WA pay transparency
laws). This module pulls those ranges out of description text so
ScrapedJobListing.salary_min/salary_max can be populated — which feeds the
HAS specificity signal, the salary filter, card display, and (eventually) the
employer-behavior salary column.

Design principles:
- Conservative: a missed salary is a small loss; an invented one is a lie on
  a trust-branded board. When in doubt, return None.
- All results are ANNUALIZED USD (hourly x2080, weekly x52, monthly x12).
- Dependency-free (re / html / decimal only) so it's cheap to unit test.

Public API:
    extract_salary_range(text) -> (min, max) | None
        min/max are Decimals; one side may be None ("from $X" / "up to $X"),
        never both.
"""
import html
import re
from decimal import Decimal

# Strip HTML tags — descriptions arrive as HTML fragments.
_TAG_RE = re.compile(r'<[^>]+>')

# A money amount: $185,000 / $185K / $62.50. First amount requires the $;
# in ranges the second $ is optional ("$185-240K", "$50,000 - 60,000").
_AMT_FIRST = r'\$\s*(\d{1,3}(?:,\d{3})+|\d+(?:\.\d{1,2})?)\s*([kK])?'
_AMT_SECOND = r'(?:\$\s*)?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d{1,2})?)\s*([kK])?'

# Optional period token that can sit between the first amount and the dash:
# "$45/hr - $55/hr", "$120,000/year - $150,000/year"
_MID_PERIOD = r'(?:\s*/\s*(?:hr|hour|yr|year|wk|week|mo|month))?'

_RANGE_RE = re.compile(
    _AMT_FIRST + _MID_PERIOD + r'\s*(?:-|–|—|−|\bto\b|\bthrough\b)\s*' + _AMT_SECOND
)
_SINGLE_RE = re.compile(_AMT_FIRST)

# Period markers looked up in the context window around a match
_HOURLY_RE = re.compile(r'per\s*hour|/\s*(?:hr|hour)\b|hourly', re.I)
_WEEKLY_RE = re.compile(r'per\s*week|/\s*(?:wk|week)\b|weekly', re.I)
_MONTHLY_RE = re.compile(r'per\s*month|/\s*(?:mo|month)\b|monthly', re.I)
_ANNUAL_RE = re.compile(r'per\s*(?:year|annum)|/\s*(?:yr|year)\b|annual|yearly|a\s*year', re.I)

# Words that mark a money mention as NOT base pay
_EXCLUDE_RE = re.compile(
    r'bonus|sign[\s-]?on|401|retirement|reimburse|referral|stipend|'
    r'allowance|deductible|premium|discount|credit|billion|million|'
    r'\bfund|revenue|valuation|per\s*diem|prize',
    re.I,
)

# Non-USD currency markers around the amount
_NON_USD_RE = re.compile(r'CAD|C\$|CA\$|AUD|A\$|NZ\$|SGD|HK\$|MXN|£|€|₹', re.I)

# Positive salary context (required for single values; a bonus for ranges)
_CONTEXT_RE = re.compile(
    r'salary|compensation|pay\b|base\s+pay|pay\s+range|base\s+range|'
    r'wage|remuneration|earn|rate\b|range\b',
    re.I,
)

_SENTENCE_END_RE = re.compile(r'[.;!?\n]')

# Sanity bounds on the final ANNUAL figure
_MIN_ANNUAL = Decimal(15000)
_MAX_ANNUAL = Decimal(1200000)
_MAX_RATIO = 6  # max/min beyond this is probably not a base-pay range

_WINDOW = 90  # max chars of context inspected on each side of a match


def _to_number(num_str, k_suffix):
    value = Decimal(num_str.replace(',', ''))
    if k_suffix:
        value *= 1000
    return value


def _context(clean, start, end):
    """Context window clipped to the sentence containing the match, so a
    bonus mentioned in the NEXT sentence doesn't poison a valid range (and a
    valid range isn't rescued by salary words from an unrelated sentence)."""
    before = clean[max(0, start - _WINDOW):start]
    ends = [m.end() for m in _SENTENCE_END_RE.finditer(before)]
    if ends:
        before = before[ends[-1]:]
    after = clean[end:end + _WINDOW]
    m = _SENTENCE_END_RE.search(after)
    if m:
        after = after[:m.start()]
    return before + after


def _annualize(value, context):
    """Convert a raw amount to annual USD using period markers in context,
    falling back to magnitude heuristics. Returns None if ambiguous."""
    if _HOURLY_RE.search(context):
        return value * 2080
    if _WEEKLY_RE.search(context):
        return value * 52
    if _MONTHLY_RE.search(context):
        return value * 12
    if _ANNUAL_RE.search(context):
        return value
    # No explicit period: infer from magnitude.
    if value < 250:
        # Reads like an hourly rate ($18.50, $95). Only trust it if the
        # context at least smells like pay.
        if _CONTEXT_RE.search(context):
            return value * 2080
        return None
    if value < 20000:
        # Could be weekly, monthly, or a bonus figure — too ambiguous.
        return None
    return value  # annual-magnitude number


def _plain_text(text):
    # Unescape BEFORE stripping tags: descriptions arrive double-escaped
    # (&lt;p&gt; / &amp;ndash;), so entities must resolve to real tags/dashes
    # first or the tag-strip and range regexes never see them. Two passes
    # handle the double encoding; a second strip catches tags the first
    # unescape revealed.
    unescaped = html.unescape(html.unescape(text or ''))
    return _TAG_RE.sub(' ', unescaped)


def extract_salary_range(text, max_scan=80000):
    """
    Extract an annualized USD salary from free text.

    Returns (min, max) as Decimals — one side may be None for "from $X" /
    "up to $X" singles — or None when nothing trustworthy is found.
    """
    if not text:
        return None
    clean = _plain_text(text)[:max_scan]

    # ---- Pass 1: explicit ranges ------------------------------------
    range_spans = []
    for m in _RANGE_RE.finditer(clean):
        range_spans.append((m.start(), m.end()))
        ctx = _context(clean, m.start(), m.end())
        if _EXCLUDE_RE.search(ctx) or _NON_USD_RE.search(ctx):
            continue
        lo = _to_number(m.group(1), m.group(2))
        hi = _to_number(m.group(3), m.group(4))
        # "$185-240K": K on the high side only distributes to both
        if m.group(4) and not m.group(2) and lo < 1000 and hi >= 1000:
            lo *= 1000
        lo_a = _annualize(lo, ctx)
        hi_a = _annualize(hi, ctx)
        if lo_a is None or hi_a is None:
            continue
        if lo_a > hi_a:
            continue
        if not (_MIN_ANNUAL <= lo_a and hi_a <= _MAX_ANNUAL):
            continue
        if lo_a > 0 and hi_a / lo_a > _MAX_RATIO:
            continue
        return (lo_a, hi_a)

    # ---- Pass 2: single amounts with strong pay context --------------
    for m in _SINGLE_RE.finditer(clean):
        # A single inside an (already rejected) range must not resurrect it.
        if any(s <= m.start() < e for s, e in range_spans):
            continue
        ctx = _context(clean, m.start(), m.end())
        if not _CONTEXT_RE.search(ctx):
            continue
        if _EXCLUDE_RE.search(ctx) or _NON_USD_RE.search(ctx):
            continue
        value = _to_number(m.group(1), m.group(2))
        annual = _annualize(value, ctx)
        if annual is None or not (_MIN_ANNUAL <= annual <= _MAX_ANNUAL):
            continue
        before = clean[max(0, m.start() - 30): m.start()]
        if re.search(r'up\s*to\s*$', before, re.I):
            return (None, annual)
        return (annual, None)

    return None
