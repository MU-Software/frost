# Add custom plugins here.
# If you want to make git not to track this file anymore,
# use `git update-index --skip-worktree app/plugin/__init__.py`

import flask
import flask_limiter
import flask_limiter.util
import flask_migrate

import app.database as db_module

db = db_module.db


def init_app(app: flask.Flask):
    # Do additional plugin set-ups here
    runable_app = app

    # Rate-limit our API
    limiter_storage_url = "redis://"
    redis_password = app.config.get("REDIS_PASSWORD", None)
    if redis_password:
        limiter_storage_url += f":{redis_password}@"
    limiter_storage_url += f'{app.config.get("REDIS_HOST")}:{app.config.get("REDIS_PORT")}'

    limiter = flask_limiter.Limiter(  # noqa: F841
        runable_app,
        key_func=flask_limiter.util.get_remote_address,
        default_limits=["3 per second"],
        storage_uri=limiter_storage_url,
    )

    # Migrate database
    migrate = flask_migrate.Migrate(  # noqa: F841
        runable_app,
        db,
        directory="app/database/migrations",
    )

    # init_app must return app
    return runable_app
