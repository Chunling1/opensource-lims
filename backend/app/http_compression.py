"""Lossless gzip for public assets and selected read-only list responses."""
import gzip
from flask import request

LIST_PATHS = {
              '/api/entrust/query', '/api/reports/query', '/api/samples/query',
              '/api/customers/query'}
ASSET_TYPES = {'application/javascript', 'text/javascript', 'text/css'}


def install_compression(app):
    @app.after_request
    def compress_response(response):
        asset = request.path.startswith('/assets/') and response.mimetype in ASSET_TYPES
        listing = request.path in LIST_PATHS and response.mimetype == 'application/json'
        if not (asset or listing) or response.status_code != 200 or request.method == 'HEAD':
            return response
        response.vary.add('Accept-Encoding')
        if (request.accept_encodings['gzip'] <= 0 or 'Content-Encoding' in response.headers
                or 'Content-Range' in response.headers or request.headers.get('Range')
                or 'no-transform' in response.headers.get('Cache-Control', '')
                or response.headers.get('Content-Disposition', '').lower().startswith('attachment')):
            return response
        length = response.content_length
        if length is None or length < 2048 or length > 8 * 1024 * 1024:
            return response
        if response.is_streamed and not asset:
            return response
        # Static send_file responses are bounded by Content-Length above.
        response.direct_passthrough = False
        original = response.response
        data = response.get_data()
        compressed = gzip.compress(data, compresslevel=5, mtime=0)
        if len(compressed) < len(data):
            response.set_data(compressed)
            response.headers['Content-Encoding'] = 'gzip'
            etag, _weak = response.get_etag()
            if etag:
                response.set_etag(etag, weak=True)
        if hasattr(original, 'close'):
            original.close()
        return response
