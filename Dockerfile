FROM python:3.12-slim@sha256:46cb7cc2877e60fbd5e21a9ae6115c30ace7a077b9f8772da879e4590c18c2e3

COPY --from=ghcr.io/astral-sh/uv:0.11.3@sha256:90bbb3c16635e9627f49eec6539f956d70746c409209041800a0280b93152823 /uv /uvx /bin/

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
