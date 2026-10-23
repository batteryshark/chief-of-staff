"""Routing observations, never proof of reconciled tools or source ownership."""
import hashlib
import json
import re
from email.utils import parsedate_to_datetime

from .policy import instant, number, timestamp

SHORT_COOLDOWN = 300  # Ambiguous throughput 429: five minutes, not a weekly ban.


def quota_failure(failure, now):
    if not isinstance(failure, dict):
        raise ValueError('provider_failure must be an object')
    message = failure.get('message', '')
    if not isinstance(message, str) or not message.strip() or len(message) > 16000:
        raise ValueError('provider_failure requires a bounded provider error message')
    status = failure.get('status')
    if status != 429 and not re.search(r'individual quota reached|quota (?:exceeded|exhausted)|rate[ -]?limit|resource_exhausted|too many requests', message, re.I):
        return None
    observed = instant(failure.get('observed_at')) if 'observed_at' in failure else now
    if observed is None or observed > now + 5:
        raise ValueError('invalid failure observed_at')
    until = instant(failure.get('reset_at'))
    hint = 'explicit reset_at'
    retry = failure.get('retry_after')
    if until is None and retry is not None:
        try:
            seconds = float(retry)
            until = observed + seconds if number(seconds) and seconds >= 0 else None
        except (TypeError, ValueError):
            try:
                until = parsedate_to_datetime(str(retry)).timestamp()
            except (TypeError, ValueError, OverflowError):
                until = instant(retry)
        hint = 'Retry-After'
    if until is None:
        match = re.search(r'(?:resets?\s*(?:in|after)|retry[ -]?after\s*[:=]?)\s*(?:(?:about|approximately|~)\s*)?(\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)?\b', message, re.I)
        if match:
            unit = (match[2] or 's').lower()[0]
            until = observed + float(match[1]) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit]
            hint = 'provider relative hint (approximate)' if re.search(r'about|approximately|~', match[0], re.I) else 'provider relative hint'
    if until is None:
        until, hint = observed + SHORT_COOLDOWN, 'bounded 5-minute fallback; reset unknown'
    # Hash only a stable failure identity, not the observation/re-report clock.
    key = failure.get('key') or hashlib.sha256(json.dumps([message, status, retry, failure.get('reset_at')], sort_keys=True).encode()).hexdigest()
    if not isinstance(key, str) or not key or len(key) > 256:
        raise ValueError('invalid failure key')
    return dict(key=key, observed_at=timestamp(observed), until=timestamp(until),
                reason='provider quota/rate-limit', reset_basis=hint,
                provenance=failure.get('provenance', 'reported'))
