FROM python:3.13.13-slim-bookworm AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/workspace

WORKDIR /workspace

RUN apt-get update \
    && apt-get install --yes --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 waterbridge \
    && useradd --uid 10001 --gid waterbridge --create-home waterbridge \
    && install -d --owner=waterbridge --group=waterbridge /home/waterbridge/.cache

COPY ai/requirements-linux.lock /tmp/requirements-linux.lock
RUN python -m pip install pip==26.1.2 \
    && python -m pip install \
      --no-deps \
      --only-binary=:all: \
      --index-url https://pypi.org/simple \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      --requirement /tmp/requirements-linux.lock \
    && python -m pip check

FROM dependencies AS qa

ARG RELEASE_SHA
ENV RELEASE_SHA=${RELEASE_SHA}

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && /usr/bin/git init --quiet /workspace

COPY scripts/deployment/production/qa-git-metadata.sh /usr/local/bin/git
RUN chmod 0755 /usr/local/bin/git \
    && python -c "import os,re; assert re.fullmatch(r'[0-9a-f]{40}', os.environ['RELEASE_SHA'])"

COPY --chown=waterbridge:waterbridge .gitignore /workspace/.gitignore
COPY --chown=waterbridge:waterbridge .gitattributes /workspace/.gitattributes
COPY --chown=waterbridge:waterbridge ai/ /workspace/ai/
COPY --chown=waterbridge:waterbridge contracts/ /workspace/contracts/
COPY --chown=waterbridge:waterbridge data/ /workspace/data/
RUN chown --recursive waterbridge:waterbridge /workspace

USER waterbridge

RUN python -m pytest ai/tests/unit -q -p no:cacheprovider

FROM dependencies AS runtime

COPY --chown=waterbridge:waterbridge ai/ /workspace/ai/
COPY --chown=waterbridge:waterbridge data/processed/structured/rag/mvp/ /workspace/data/processed/structured/rag/mvp/

USER waterbridge

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=6 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/v1/ai/health', timeout=3)" || exit 1

CMD ["python", "-m", "uvicorn", "ai.app.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
