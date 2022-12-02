FROM python:3.11-bullseye as base

FROM base as builder

RUN set -eux; \
    apt-get update; \
    apt-get install -y \
        curl \
        openssh-client \
        gcc \
        git \
        libpq-dev \
        python3-dev

RUN set -eux; \
    pip install --upgrade pip; \
    curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="${PATH}:/root/.local/bin:"

COPY ../poetry.lock ../pyproject.toml ./

RUN set -eux; \
    poetry config experimental.system-git-client true; \
    poetry config virtualenvs.create false; \
    poetry install --only main --no-interaction --no-ansi

FROM base as runtime

ENV TZ=Asia/Seoul
ENV PYTHONIOENCODING=UTF-8

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        curl \
        wget \
        ca-certificates \
        gnupg \
        lsb-release \
        cron \
        supervisor

COPY --from=builder /usr/local/bin/celery /usr/local/bin/celery
COPY --from=builder /usr/local/bin/dotenv /usr/local/bin/dotenv
COPY --from=builder /usr/local/bin/flask /usr/local/bin/flask
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn
COPY --from=builder /usr/local/lib/python3.11/lib-dynload /usr/local/lib/python3.11/lib-dynload
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY ../swagger_ui_dist /swagger_ui_dist

# Make docker to always copy app directory so that source code can be refreshed.
ARG INVALIDATE_CACHE_DATE=unknown
RUN echo INVALIDATE_CACHE_DATE

COPY ../app/ /app
