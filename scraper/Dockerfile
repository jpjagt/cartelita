# syntax=docker/dockerfile:1
FROM python:3.14-slim

# tesseract-ocr is required by the casa_figari OCR scraper (pytesseract).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# uv: copy the static binary from the official image (no pip bootstrap needed).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first (cached) from the lockfile, then the project.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now copy the source and install the project itself (provides the `cartelera` script).
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Idle by default: scraping happens only in the nightly Coolify Scheduled Task
# (`cartelera migrate && cartelera run all`, exec'd in this container). A
# scraping CMD would exit when done, Coolify would restart the container, and
# every site would be re-scraped every ~15 minutes, all day.
CMD ["sleep", "infinity"]
