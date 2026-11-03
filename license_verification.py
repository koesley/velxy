"""Server-side Payhip license verification with sanitized diagnostics."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class LicenseError(Exception):
    pass


class LicenseUnavailable(Exception):
    pass


def _safe_error(exc):
    """Return only allowlisted, non-sensitive API error information."""
    try:
        raw = exc.read(4096)
        payload = json.loads(raw)
    except (ValueError, UnicodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    # Do not forward arbitrary server messages: they may echo keys or secrets.
    for field in ('code', 'error_code', 'status'):
        value = payload.get(field)
        if isinstance(value, (str, int)):
            s = str(value)
            if 0 < len(s) <= 48 and all(c.isalnum() or c in '_-' for c in s):
                return '%s=%s' % (field, s)
    return None


def verify(key, email):
    secret = os.getenv('VELXTRIA_PAYHIP_PRODUCT_SECRET', '').strip()
    product = os.getenv('VELXTRIA_PAYHIP_PRODUCT_KEY', '').strip()
    if not secret or not product:
        raise LicenseUnavailable('License verification is not configured.')
    if not key or len(key) > 120 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise LicenseError('Enter a valid license key.')

    url = 'https://payhip.com/api/v2/license/verify?' + urllib.parse.urlencode({'license_key': key})
    request = urllib.request.Request(url, headers={
        'product-secret-key': secret,
        'Accept': 'application/json',
        'User-Agent': 'VELXTRIA-License-Verification/1.0',
    })
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            if response.status != 200:
                raise LicenseUnavailable('Payhip returned an unexpected response.')
            data = json.loads(response.read(32768))
    except urllib.error.HTTPError as exc:
        detail = _safe_error(exc)
        suffix = ('; ' + detail) if detail else ''
        if exc.code in (400, 404, 422):
            raise LicenseError('Payhip rejected this license request (HTTP %d%s).' % (exc.code, suffix)) from exc
        if exc.code in (401, 403):
            raise LicenseUnavailable('Payhip authentication failed (HTTP %d%s). Check the product secret.' % (exc.code, suffix)) from exc
        raise LicenseUnavailable('Payhip verification returned HTTP %d%s.' % (exc.code, suffix)) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LicenseUnavailable('Payhip connection failed. Check network access and try again.') from exc
    except (ValueError, UnicodeError) as exc:
        raise LicenseUnavailable('Payhip returned an unreadable response.') from exc

    license_info = data.get('data') if isinstance(data, dict) else None
    if not isinstance(license_info, dict):
        raise LicenseError('License not found or Payhip returned no license data.')
    if license_info.get('enabled') is not True:
        raise LicenseError('License is disabled or refunded.')
    if license_info.get('product_link') != product:
        raise LicenseError('License is for another product.')
    if str(license_info.get('buyer_email', '')).strip().casefold() != email.strip().casefold():
        raise LicenseError('Sign in using the email used at Payhip checkout.')
    if license_info.get('license_key') != key:
        raise LicenseError('License mismatch.')
    return license_info
