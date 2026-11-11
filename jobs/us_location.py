"""
Single source of truth for "is this a US location?".

Mirrors the semantics of the old /jobs/ US-only filter exactly:
  - contains "United States" or ", US"            (case-insensitive)
  - ends with ", XX"                              (case-SENSITIVE state code)
  - contains ", XX "                              (case-insensitive)

The result is denormalized onto ScrapedJobListing.is_us (set in save(), and
backfilled in migration 0029) so the browse page can filter on an indexed
boolean instead of running ~100 LIKEs over every published row.
"""
import re

US_STATES = (
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
    'DC',
)

_STATE_ALT = '|'.join(US_STATES)

# Postgres-flavoured patterns for the SQL backfill (same alternation).
PG_ANYWHERE_CI = r'united states|, us'
PG_ENDS_WITH_CS = rf', ({_STATE_ALT})$'
PG_STATE_SPACE_CI = rf', ({_STATE_ALT}) '

_ANYWHERE_RE = re.compile(r'united states|, us', re.IGNORECASE)
_ENDS_WITH_RE = re.compile(rf', (?:{_STATE_ALT})$')
_STATE_SPACE_RE = re.compile(rf', (?:{_STATE_ALT}) ', re.IGNORECASE)


def is_us_location(location):
    if not location:
        return False
    return bool(
        _ANYWHERE_RE.search(location)
        or _ENDS_WITH_RE.search(location)
        or _STATE_SPACE_RE.search(location)
    )
