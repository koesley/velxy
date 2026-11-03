"""Server-side Payhip v2 license validation. Never expose product secret to browsers."""
import json, os, urllib.parse, urllib.request, urllib.error

class LicenseError(Exception): pass
class LicenseUnavailable(Exception): pass

def verify(key, email):
    secret=os.getenv('VELXTRIA_PAYHIP_PRODUCT_SECRET','').strip()
    product=os.getenv('VELXTRIA_PAYHIP_PRODUCT_KEY','').strip()
    if not secret or not product:
        raise LicenseUnavailable('License verification is not configured.')
    if not key or len(key)>120 or any(ord(c)<33 or ord(c)>126 for c in key):
        raise LicenseError('Enter a valid license key.')
    url='https://payhip.com/api/v2/license/verify?'+urllib.parse.urlencode({'license_key':key})
    request=urllib.request.Request(url,headers={'product-secret-key':secret,'Accept':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=8) as response:
            if response.status != 200: raise LicenseUnavailable('License provider unavailable.')
            data=json.loads(response.read(32768))
    except (urllib.error.URLError,TimeoutError,ValueError,UnicodeError) as exc:
        raise LicenseUnavailable('Could not contact Payhip. Try again later.') from exc
    license_info=data.get('data') if isinstance(data,dict) else None
    if not isinstance(license_info,dict): raise LicenseError('License not found.')
    if license_info.get('enabled') is not True: raise LicenseError('License is disabled or refunded.')
    if license_info.get('product_link') != product: raise LicenseError('License is for another product.')
    if str(license_info.get('buyer_email','')).strip().casefold() != email.strip().casefold():
        raise LicenseError('Sign in using the email used at Payhip checkout.')
    if license_info.get('license_key') != key: raise LicenseError('License mismatch.')
    return license_info
