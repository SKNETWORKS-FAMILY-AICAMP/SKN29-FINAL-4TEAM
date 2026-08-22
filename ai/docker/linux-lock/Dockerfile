FROM ubuntu:24.04

ARG PYTHON_VERSION=3.13.13
ARG PYTHON_SOURCE_SHA256=2ab91ff401783ccca64f75d10c882e957bdfd60e2bf5a72f8421793729b78a71
ARG PIP_VERSION=26.1.2

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        libbz2-dev \
        libffi-dev \
        libgdbm-dev \
        liblzma-dev \
        libncursesw5-dev \
        libreadline-dev \
        libsqlite3-dev \
        libssl-dev \
        tk-dev \
        uuid-dev \
        xz-utils \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl --fail --location --show-error \
        "https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tar.xz" \
        --output /tmp/python.tar.xz \
    && echo "${PYTHON_SOURCE_SHA256}  /tmp/python.tar.xz" | sha256sum --check --strict \
    && mkdir /tmp/python-source \
    && tar --extract --xz --file /tmp/python.tar.xz --directory /tmp/python-source --strip-components=1 \
    && cd /tmp/python-source \
    && ./configure --prefix="/opt/python/${PYTHON_VERSION}" --with-ensurepip=install \
    && make --jobs="$(nproc)" \
    && make install \
    && ln -s "/opt/python/${PYTHON_VERSION}/bin/python3.13" /usr/local/bin/python \
    && rm -rf /tmp/python-source /tmp/python.tar.xz

RUN python -m pip install --disable-pip-version-check --no-cache-dir "pip==${PIP_VERSION}"

# Several AI unit tests record Git identity. Keep this in the verification image,
# while dependency resolution remains fully controlled by the Python lock.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

CMD ["python", "ai/scripts/generate_linux_ci_lock.py"]
