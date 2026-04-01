FROM python:3.12-slim

# System deps for pyaudio, ir-ctl, and systemctl (for librespot restart)
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    v4l-utils \
    openssh-client \
    systemd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir "."

# Copy source
COPY src/ src/

# Install the package
RUN pip install --no-cache-dir -e .

# Create dirs and make writable for non-root user
RUN mkdir -p ir-codes && chown -R 1000:1000 /app

CMD ["python", "-m", "clawdia.main"]
