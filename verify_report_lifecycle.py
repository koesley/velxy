"""Opt-in end-to-end durability check for VELXTRIA private report storage.

Run only with explicit --run-live. Creates a synthetic, uniquely named object,
reads it back, verifies exact bytes, and removes it. Never touches customer
objects. Does not print credentials or service error bodies.
"""
import argparse
import hashlib
import io
import json
import secrets
import sys
import urllib.parse
import urllib.request
import zipfile


def synthetic_zip():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('healthcheck.txt', 'VELXTRIA synthetic storage verification\n')
    return stream.getvalue()


def verify(storage=None, identifier=None):
    import persistent
    if not (persistent.REMOTE and persistent.URL and persistent.KEY):
        return 'not_configured'
    storage = storage or persistent
    identifier = identifier or secrets.token_hex(20)
    # Reserved namespace, never a real customer ID.
    owner = '_velxtria_storage_probe'
    payload = synthetic_zip()
    outcome = 'failed'
    # Always attempt cleanup, even if the upload reports an error after
    # the remote service has already accepted the object.
    try:
        storage.store(owner, identifier, payload, None)
        retrieved = storage.retrieve(owner, identifier, None)
        if hashlib.sha256(retrieved).digest() != hashlib.sha256(payload).digest():
            outcome = 'integrity_failed'
        else:
            outcome = 'connected'
    except Exception:
        outcome = 'failed'
    try:
        remove_probe_object(persistent.URL, persistent.KEY,
                            persistent.BUCKET, owner, identifier)
    except Exception:
        return 'cleanup_failed'
    return outcome


def remove_probe_object(url, key, bucket, owner, identifier, opener=None):
    """Supabase Storage's documented bulk-remove API (not DELETE object URL)."""
    prefix = owner + '/' + identifier + '.zip'
    endpoint = url.rstrip('/') + '/storage/v1/object/remove/' + urllib.parse.quote(bucket, safe='')
    payload = json.dumps({'prefixes': [prefix]}).encode()
    request = urllib.request.Request(endpoint, data=payload, method='POST', headers={
        'apikey': key, 'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/json',
    })
    with (opener or urllib.request.urlopen)(request, timeout=15) as response:
        return response.read(65536)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Opt-in synthetic Supabase storage lifecycle verification')
    parser.add_argument('--run-live', action='store_true', help='Create, read and remove one synthetic report object')
    args = parser.parse_args(argv)
    if not args.run_live:
        print('No storage changes made. Pass --run-live to verify the synthetic report lifecycle.')
        return 2
    result = verify()
    print('VELXTRIA synthetic report lifecycle:', result)
    return 0 if result == 'connected' else 1


if __name__ == '__main__':
    sys.exit(main())
