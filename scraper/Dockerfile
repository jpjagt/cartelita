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

# Headless Chromium for cartelera.scrapers.browser (queue gates / bot checks
# HTTP can't pass, e.g. De Doelen's csq_token). Only the slim
# `chromium-headless-shell` (no full Chrome, no Firefox/WebKit) plus its apt
# system libs (`--with-deps`; Playwright supports Debian 13/trixie, this
# image's base). Adds roughly 250-300 MB to the image. A fixed browsers path
# keeps it independent of $HOME.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN /app/.venv/bin/playwright install --with-deps chromium-headless-shell \
    && rm -rf /var/lib/apt/lists/*

# Now copy the source and install the project itself (provides the `cartelera` script).
COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Idle by default: scraping happens only in the nightly Coolify Scheduled Task
# (`cartelera migrate && cartelera run all`, exec'd in this container). A
# scraping CMD would exit when done, Coolify would restart the container, and
# every site would be re-scraped every ~15 minutes, all day.
CMD ["sleep", "infinity"]
