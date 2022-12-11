import os

import celery

REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = os.environ.get("REDIS_PORT")
CELERY_BACKEND_URL = f"redis://{f':{REDIS_PASSWORD}@' if REDIS_PASSWORD else ''}{REDIS_HOST}:{REDIS_PORT}"
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", CELERY_BACKEND_URL)

internal_celery_app: celery.Celery = None


def init_celery_app():
    global internal_celery_app

    if internal_celery_app is None:
        internal_celery_app = celery.Celery(
            main="userdbmod1",
            backend=CELERY_BACKEND_URL,
            broker=CELERY_BROKER_URL,
        )
        internal_celery_app.conf.task_ignore_result = True

    import app.worker.project_worker as project_worker  # noqa: F401

    return internal_celery_app


celery_app: celery.Celery = init_celery_app()
