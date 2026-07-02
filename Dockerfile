FROM python:3.12-slim@sha256:ec948fa5f90f4f8907e89f4800cfd2d2e91e391a4bce4a6afa77ba265bc3a2fe

COPY --from=ghcr.io/astral-sh/uv:0.11.13@sha256:841c8e6fe30a8b07b4478d12d0c608cba6de66102d29d65d1cc423af86051563 /uv /uvx /bin/

# System deps for pyaudio, ir-ctl, and systemctl (for librespot restart)
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    v4l-utils \
    openssh-client \
    systemd \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra voice --no-install-project

# Remove build tools to keep image smaller
RUN apt-get purge -y --auto-remove build-essential

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY src/ src/

RUN uv sync --frozen --no-dev --extra voice

# Create user so SSH works when running as uid 1000
RUN groupadd -g 1000 clawdia && useradd -u 1000 -g 1000 -d /home/vossi -s /bin/bash clawdia && mkdir -p /home/vossi

# Create dirs and make writable for non-root user
RUN mkdir -p ir-codes && chown -R 1000:1000 /app

CMD ["python", "-m", "clawdia.main"]
