FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt /tmp/agent-guild-orchestra-requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/agent-guild-orchestra-requirements.txt

CMD ["python", "--version"]
