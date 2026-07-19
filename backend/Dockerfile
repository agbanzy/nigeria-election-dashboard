# Single backend image shared by every backend component on DO App Platform
# (web + scraper worker + migrate/seed jobs). Building once and reusing the
# image replaces 7 identical buildpack `pip install` builds per deploy (F-904).
#
# Build for the platform DO runs on (amd64), not the local arch:
#   doctl registry login
#   docker build --platform linux/amd64 \
#     -t registry.digitalocean.com/docufy/nigeria-election-backend:latest backend/
#   docker push registry.digitalocean.com/docufy/nigeria-election-backend:latest
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps first for layer caching (psycopg[binary]/numpy/Pillow ship
# manylinux wheels, so no build toolchain is needed).
COPY requirements.txt ./
RUN pip install -r requirements.txt

# App code, migrations, alembic.ini (the migrate/seed jobs need these).
COPY . .

EXPOSE 8080

# Default command = the web service. The scraper worker and the PRE/POST_DEPLOY
# jobs each override this via run_command in the app spec.
CMD ["gunicorn", "-w", "2", "--threads", "4", "-k", "gthread", \
     "-b", "0.0.0.0:8080", "app.wsgi:app", "--timeout", "120"]
