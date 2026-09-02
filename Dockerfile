FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6

COPY --from=ghcr.io/astral-sh/uv:0.11.26@sha256:3d868e555f8f1dbc324afa005066cd11e1053fc4743b9808ca8025283e65efa5 /uv /uvx /bin/

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
