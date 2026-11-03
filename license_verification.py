"""Server-side Payhip license verification. Never expose secrets or license keys."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class LicenseError(Exception):
    pass


class LicenseUnavailable(Exception):
    pass


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
        # Report only HTTP status, never response bodies (which may contain sensitive data).
        if exc.code in (400, 404, 422):
            raise LicenseError('Payhip rejected this license request (HTTP %d).' % exc.code) from exc
        if exc.code in (401, 403):
            raise LicenseUnavailable('Payhip authentication failed (HTTP %d). Check the product secret.' % exc.code) from exc
        raise LicenseUnavailable('Payhip verification returned HTTP %d.' % exc.code) from exc
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
