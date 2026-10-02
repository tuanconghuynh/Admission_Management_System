"""Signed, expiring print previews. No database writes until confirmation."""
import base64
import hashlib
import hmac
import json
import time
import uuid
import zlib
from fastapi import HTTPException
from app.core.config import settings


def print_headers(request, ids, paper):
    data = {'uid': request.session.get('uid'), 'ids': list(dict.fromkeys(ids)),
        'paper': paper, 'nonce': str(uuid.uuid4()), 'issued': int(time.time())}
    raw = base64.urlsafe_b64encode(zlib.compress(json.dumps(data, separators=(',', ':')).encode())).decode()
    signature = hmac.new(settings.SESSION_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return {'X-Print-Token': raw + '.' + signature, 'Cache-Control': 'no-store'}


def read_print_token(token, uid):
    try:
        raw, signature = token.rsplit('.', 1)
        expected = hmac.new(settings.SESSION_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(base64.urlsafe_b64decode(raw), 250000)
        if not inflater.eof:
            raise ValueError()
        data = json.loads(decoded)
        if data['uid'] != uid or not 0 <= time.time() - data['issued'] <= 7200:
            raise ValueError()
        if not data['ids'] or data['paper'] not in {'A4', 'A5', 'EMAILA5', 'COVER', 'POSTAL'}:
            raise ValueError()
        return data
    except Exception:
        raise HTTPException(422, 'Phiên xem bản in không hợp lệ hoặc đã hết hạn. Hãy mở lại bản in.')
