FROM python:3.13-slim-bookworm

RUN apt-get update && apt-get install -y \
    curl \
    bzip2 \
    && rm -rf /var/lib/apt/lists/*

ARG MICROMAMBA_VERSION=2.9.0
# The platform comes from the build container itself, so the binary always matches the
# image being built — with or without BuildKit, and under --platform. micromamba names
# x86_64 "linux-64" and every other machine "linux-<machine>".
RUN MAMBA_PLATFORM="linux-$(uname -m | sed 's/^x86_64$/64/')" \
    && curl -Ls "https://micro.mamba.pm/api/micromamba/${MAMBA_PLATFORM}/${MICROMAMBA_VERSION}" \
    | tar -xvj -C /usr/local bin/micromamba && chmod +x /usr/local/bin/micromamba

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.4.18 /uv /bin/uv

COPY pyproject.toml /app/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-dev --no-install-project

COPY . /app/

ENV PYTHONPATH=/app

CMD ["uv", "run", "python", "main.py"]
