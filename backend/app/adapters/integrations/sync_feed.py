"""Bounded consistent pagination, optionally reusing a verified contract revision."""
import hashlib, json, threading, time
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
from urllib.error import HTTPError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

_lock = threading.Lock()
_snapshot = None

def fetch_rows(url, secret, *, reuse_revision=False):
    global _snapshot
    if not reuse_revision:
        return _fetch(url, secret)[1]
    key = (url, hashlib.sha256(secret.encode()).digest())
    with _lock:
        cached = _snapshot[1] if _snapshot and _snapshot[0] == key else None
        try:
            result = _fetch(url, secret, cached)
        except Exception:
            _snapshot = None
            raise
        # Immutable JSON avoids Python's costly recursive deepcopy of every
        # nested evidence object while keeping callers isolated from the cache.
        if not isinstance(result[1], bytes):
            result = (result[0], json.dumps(result[1], ensure_ascii=False).encode(), result[2])
        _snapshot = (key, result)
        return json.loads(result[1])

def _fetch(url, secret, cached=None):
    parsed = urlsplit(url)
    if parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('LOCAL_FEED_REQUIRED')
    started = time.monotonic()
    opener = build_opener(ProxyHandler({}), NoRedirect())
    for attempt in range(3):
        rows, cursor, revision, seen, first_hash = [], '', '', set(), None
        for page in range(2501):
            if time.monotonic() - started > 20:
                raise RuntimeError('FEED_TIME_LIMIT')
            query = dict(parse_qsl(parsed.query))
            query.update(page='3', limit='200', cursor=cursor, revision=revision)
            target = urlunsplit(parsed._replace(query=urlencode(query)))
            try:
                with opener.open(Request(target, headers={'Authorization': 'Bearer '+secret}), timeout=3) as r:
                    body = r.read(5 * 1024**2 + 1)
            except HTTPError as exc:
                if exc.code == 409: break
                raise
            if len(body) > 5 * 1024**2: raise RuntimeError('FEED_SIZE_LIMIT')
            value = json.loads(body)
            current = value.get('revision')
            if value.get('status') != 'ok' or not isinstance(value.get('rows'), list) or current is None:
                raise RuntimeError('FEED_PROTOCOL')
            if revision and current != revision: break
            if page == 0:
                first_hash = hashlib.sha256(body).digest()
                if cached is not None and cached[0] == current and cached[2] == first_hash:
                    return cached
            revision = current
            rows.extend(value['rows'])
            cursor = value.get('nextCursor', '')
            if not cursor: return revision, rows, first_hash
            if cursor in seen: raise RuntimeError('FEED_CURSOR_LOOP')
            seen.add(cursor)
        else: raise RuntimeError('FEED_PAGE_LIMIT')
    raise RuntimeError('FEED_CHANGED_RETRY')
