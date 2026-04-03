FROM python:3.12-slim@sha256:3d5ed973e45820f5ba5e46bd065bd88b3a504ff0724d85980dcd05eab361fcf4

COPY --from=ghcr.io/astral-sh/uv:0.10.0@sha256:78a7ff97cd27b7124a5f3c2aefe146170793c56a1e03321dd31a289f6d82a04f /uv /uvx /bin/

# System deps for pyaudio, ir-ctl, and systemctl (for librespot restart)
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    v4l-utils \
    openssh-client \
    systemd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra voice --no-install-project

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ src/

RUN uv sync --frozen --no-dev --extra voice

# Create user so SSH works when running as uid 1000
RUN groupadd -g 1000 clawdia && useradd -u 1000 -g 1000 -d /home/vossi -s /bin/bash clawdia && mkdir -p /home/vossi

# Create dirs and make writable for non-root user
RUN mkdir -p ir-codes && chown -R 1000:1000 /app

CMD ["python", "-m", "clawdia.main"]
