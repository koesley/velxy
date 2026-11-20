"""Read-only Supabase report-storage connectivity probe.

Checks that the configured private bucket exists and is accessible with the
service credential. Does not read, create, modify, or delete customer reports.
Never returns credentials, URLs, or upstream response bodies.
"""
import json
import urllib.error
import urllib.parse
import urllib.request


def check(url=None, key=None, bucket=None, opener=None):
    import persistent
    url = persistent.URL if url is None else url
    key = persistent.KEY if key is None else key
    bucket = persistent.BUCKET if bucket is None else bucket
    if not (url and key and bucket):
        return 'not_configured'
    if not url.startswith('https://'):
        return 'failed'
    endpoint = url.rstrip('/') + '/storage/v1/bucket/' + urllib.parse.quote(bucket, safe='')
    request = urllib.request.Request(endpoint, headers={
        'apikey': key, 'Authorization': 'Bearer ' + key,
        'Accept': 'application/json',
    }, method='GET')
    try:
        with (opener or urllib.request.urlopen)(request, timeout=10) as response:
            metadata = json.loads(response.read(65536))
        if not isinstance(metadata, dict):
            return 'failed'
        # A successful request must identify the requested bucket.
        if metadata.get('id') != bucket and metadata.get('name') != bucket:
            return 'failed'
        # Report ZIPs must never be stored in a publicly accessible bucket.
        return 'connected' if metadata.get('public') is False else 'unsafe_public_bucket'
    except (ValueError, TypeError, OSError, urllib.error.URLError):
        return 'failed'


def main():
    result = check()
    print('VELXTRIA private report storage probe:', result)
    return 0 if result == 'connected' else 1


if __name__ == '__main__':
    raise SystemExit(main())
