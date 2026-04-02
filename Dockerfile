# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for lxml / pandas wheel builds
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libxml2-dev \
        libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.source="https://github.com/kyleian/bull"
LABEL org.opencontainers.image.description="S&P 500 multi-mode market scanner"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY bull/ ./bull/
COPY pyproject.toml .

# Install the package itself (no deps — already installed above)
RUN pip install --no-cache-dir --no-deps -e .

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false scanner
USER scanner

# Default: run full scan in console mode
# Override via docker run -e BULL_SCAN_MODE=bearish etc.
ENTRYPOINT ["bull", "scan"]
CMD ["--mode", "all"]
