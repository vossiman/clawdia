FROM python:3.12-slim

# System deps for pyaudio and ir-ctl
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    v4l-utils \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir "."

# Copy source
COPY src/ src/

# Install the package
RUN pip install --no-cache-dir -e .

# Create IR codes directory
RUN mkdir -p ir-codes

CMD ["python", "-m", "clawdia.main"]
