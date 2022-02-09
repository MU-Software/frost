# Add custom plugins here.
# If you want to make git not to track this file anymore,
# use `git update-index --skip-worktree app/plugin/__init__.py`

import flask


def init_app(app: flask.Flask):
    # Do additional plugin set-ups here
    # init_app must return app
    return app
