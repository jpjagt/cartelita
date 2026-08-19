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

ENV PATH="/app/.venv/bin:$PATH"

# Chromium + its system libraries for the Playwright-driven IG capture path
# (cartelera/ig/). Runs right after the dependency-only sync above (which
# already installs the playwright package) and before COPY . ., so a plain
# source edit doesn't invalidate this layer and re-download Chromium.
RUN playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Now copy the source and install the project itself (provides the `cartelera` script).
COPY . .
RUN uv sync --frozen --no-dev

# Default command; the nightly Coolify Scheduled Task overrides/wraps this with
# `cartelera migrate && cartelera run all`.
CMD ["cartelera", "run", "all"]
