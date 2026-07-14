FROM python:3.12-slim-bookworm

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY dsv_tracking/ ./dsv_tracking/
RUN uv sync --frozen --no-dev

RUN uv run playwright install --with-deps chromium

ENTRYPOINT ["uv", "run", "python", "-m", "dsv_tracking.server"]
