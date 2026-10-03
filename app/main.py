# app/main.py
import os
import uuid
import logging
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool
from sqlalchemy import text

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.status import HTTP_403_FORBIDDEN

from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from app.core.http_security import RequestSecurityMiddleware
from app.routers.auth import require_roles, get_current_user

from app.db.base import Base
from app.db.session import engine, get_db, SessionLocal
from app.routers import applicants_batch
from app.routers import health, applicants, checklist, export, batch
from app.routers import auth, admin, journal
from app.routers import account
from app.routers import applicants_email
from app.routers import dashboard
from app.routers import print_confirmation
from app.core.config import settings

# (tuỳ) audit
try:
    from app.services.audit import write_audit
except Exception:
    write_audit = None

# ================== TEMPLATE PATH CHUNG ==================
BASE_DIR = os.path.dirname(__file__)                  # .../app
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
WEB_TEMPLATES_DIR = os.path.join(TEMPLATES_DIR, "web")
templates = Jinja2Templates(directory=WEB_TEMPLATES_DIR)
from app.services.majors import MAJORS
templates.env.globals['major_catalog'] = MAJORS
# =========================================================

@asynccontextmanager
async def lifespan(application):
    if settings.AUTO_CREATE_TABLES:
        await run_in_threadpool(Base.metadata.create_all, bind=engine)
    else:
        def check_schema():
            with engine.connect() as connection:
                version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if version != "20261003_02":
                    raise RuntimeError("Run alembic upgrade head before starting this release")
        await run_in_threadpool(check_schema)
    yield
    await run_in_threadpool(engine.dispose)


app = FastAPI(lifespan=lifespan, docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
              redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
              openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json")

app.include_router(applicants_email.router, prefix="/api")
app.include_router(applicants_email.router, include_in_schema=False)
app.include_router(dashboard.router, prefix="/api")
app.include_router(dashboard.router, include_in_schema=False)
app.include_router(print_confirmation.router, prefix='/api')
app.include_router(print_confirmation.router, include_in_schema=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.ALLOWED_ORIGINS.split(",") if x.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Session cookie ----------------
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    https_only=settings.COOKIE_SECURE,
    session_cookie="__Host-ams_session" if settings.COOKIE_SECURE else "session",
    max_age=60 * 60 * 24 * 7,
    same_site="lax",
)
app.add_middleware(RequestSecurityMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[x.strip() for x in settings.ALLOWED_HOSTS.split(",") if x.strip()])

# ---------------- Correlation-ID ----------------
@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    incoming = request.headers.get("X-Correlation-ID", "")
    try:
        cid = str(uuid.UUID(incoming))
    except ValueError:
        cid = str(uuid.uuid4())
    request.state.correlation_id = cid
    resp = await call_next(request)
    resp.headers["X-Correlation-ID"] = cid
    return resp

# ---------------- Global exception handler ----------------
@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "Dữ liệu trùng hoặc tham chiếu không hợp lệ. Vui lòng tải lại và kiểm tra."})

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.getLogger("ams").error("Unhandled error path=%s correlation_id=%s", request.url.path,
        getattr(request.state, "correlation_id", ""), exc_info=(type(exc), exc, exc.__traceback__))
    try:
        if write_audit:
            with SessionLocal.begin() as db:
                write_audit(db, action="EXCEPTION", target_type="System", target_id=None,
                    status="FAILURE", new_values={"path": request.url.path, "error": type(exc).__name__}, request=request)
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"detail": "Đã xảy ra lỗi không xác định. Vui lòng thử lại."})

# ---------------- Mount routers ----------------
app.include_router(auth.router,    tags=["Auth"])
app.include_router(admin.router,   tags=["Admin"])
app.include_router(account.router, tags=["Account"])

app.include_router(health.router,     prefix="/api", tags=["Health"])
app.include_router(checklist.router,  prefix="/api", tags=["Checklist"])
app.include_router(applicants.router, prefix="/api", tags=["Applicants"])
app.include_router(applicants_batch.router, prefix="/api", tags=["Applicants (batch)"])
app.include_router(batch.router,      prefix="/api", tags=["Batch"])
app.include_router(export.router,     prefix="/api", tags=["Export"])
app.include_router(journal.router,    prefix="/api", tags=["Journal"])

for r in (health.router, checklist.router, applicants.router, applicants_batch.router, batch.router, export.router, journal.router):
    app.include_router(r, prefix="", include_in_schema=False)

# ---------------- Redirect "/" → ams_home.html ----------------
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/ams_home.html", status_code=307)

# ------------ Route chung cho các trang .html (template) ------------
@app.get("/{page_name}.html", response_class=HTMLResponse, include_in_schema=False)
async def render_page(page_name: str, request: Request, user=Depends(get_current_user)):
    if page_name != "auth_login":
        if not user or not user.is_active:
            return RedirectResponse("/login", status_code=302)
        if user.must_change_password:
            return RedirectResponse("/account?first=1", status_code=302)
        if page_name == "admin_ams" and user.role != "Admin":
            raise HTTPException(403, "Forbidden")
    # map tên file -> key active_page trong layout_ams.html
    active_map = {
        "ams_home": "home",
        "compilation": "compilation",
        "students_list": "students",
        "import_students": "import",
        "journal": "journal",
        "checklist_admin": "checklist",
        "admin_ams": "admin",
    }
    ctx = {
        "request": request,
        "active_page": active_map.get(page_name, page_name),
    }
    return templates.TemplateResponse(request, f"{page_name}.html", ctx)

# ---------------- Static files ----------------
os.makedirs(settings.receipts_path, exist_ok=True)
@app.get("/static/receipts/{filename}", include_in_schema=False)
def private_receipt(filename: str, user=Depends(require_roles("Admin", "NhanVien", "CongTacVien", "Manager"))):
    path = (settings.receipts_path / filename).resolve()
    if path.parent != settings.receipts_path or path.suffix.lower() != ".pdf" or not path.is_file():
        raise HTTPException(404, "Receipt not found")
    return FileResponse(path, media_type="application/pdf", headers={"Cache-Control": "no-store"})

app.mount(
    "/assets",
    StaticFiles(directory=os.path.join(TEMPLATES_DIR, "assets")),
    name="assets",
)
app.mount(
    "/css",
    StaticFiles(directory=os.path.join(TEMPLATES_DIR, "css")),
    name="css",
)
app.mount(
    "/js",
    StaticFiles(directory=os.path.join(TEMPLATES_DIR, "js")),
    name="js",
)
