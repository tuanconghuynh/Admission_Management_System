FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
RUN useradd --create-home --uid 10001 ams
COPY --chown=ams:ams app ./app
COPY --chown=ams:ams assets/*.ttf ./assets/
COPY --chown=ams:ams scripts ./scripts
COPY --chown=ams:ams migrations ./migrations
COPY --chown=ams:ams alembic.ini ./
RUN mkdir -p var/receipts && chown -R ams:ams var
USER ams
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
