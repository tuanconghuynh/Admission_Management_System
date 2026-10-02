"""Bound request bodies and protect cookie-authenticated mutations."""
import hmac
import secrets
from urllib.parse import parse_qs, urlsplit

from itsdangerous import BadSignature, URLSafeTimedSerializer
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings


class RequestSecurityMiddleware:
    def __init__(self, app):
        self.app = app
        self.signer = URLSafeTimedSerializer(settings.SESSION_SECRET, salt="ams-csrf")
        self.cookie_name = "__Host-ams_csrf" if settings.COOKIE_SECURE else "ams_csrf"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        token = request.cookies.get(self.cookie_name, "")
        valid = False
        try:
            self.signer.loads(token, max_age=86400)
            valid = True
        except BadSignature:
            pass
        new_token = not valid
        if new_token:
            token = self.signer.dumps(secrets.token_urlsafe(32))
        unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
        body = b""
        if unsafe:
            try:
                if int(request.headers.get("content-length", "0")) > settings.MAX_REQUEST_BYTES:
                    return await JSONResponse({"detail": "Request too large"}, 413)(scope, receive, send)
            except ValueError:
                return await JSONResponse({"detail": "Invalid content length"}, 400)(scope, receive, send)
            origin = request.headers.get("origin")
            referer = request.headers.get("referer")
            source = origin or referer
            allowed = {x.strip().rstrip("/") for x in settings.ALLOWED_ORIGINS.split(",") if x.strip()}
            allowed.add(str(request.base_url).rstrip("/"))
            if source:
                parsed = urlsplit(source)
                source_origin = f"{parsed.scheme}://{parsed.netloc}"
                if source_origin not in allowed:
                    return await JSONResponse({"detail": "Origin not allowed"}, 403)(scope, receive, send)
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body += message.get("body", b"")
                if len(body) > settings.MAX_REQUEST_BYTES:
                    return await JSONResponse({"detail": "Request too large"}, 413)(scope, receive, send)
                if not message.get("more_body", False):
                    break
            supplied = request.headers.get("x-csrf-token", "")
            if not supplied and request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
                supplied = parse_qs(body.decode("utf-8", errors="replace")).get("csrf_token", [""])[0]
            if not valid or not hmac.compare_digest(supplied.encode(), token.encode()):
                return await JSONResponse({"detail": "CSRF token invalid; reload the page"}, 403)(scope, receive, send)
        delivered = False

        async def replay():
            nonlocal delivered
            if unsafe and not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"), (b"referrer-policy", b"same-origin")])
                if settings.COOKIE_SECURE:
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                if new_token:
                    cookie = f"{self.cookie_name}={token}; Path=/; SameSite=Lax; Max-Age=86400"
                    if settings.COOKIE_SECURE:
                        cookie += "; Secure"
                    headers.append((b"set-cookie", cookie.encode()))
                if not request.url.path.startswith(("/css/", "/js/", "/assets/")):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, replay, secure_send)
