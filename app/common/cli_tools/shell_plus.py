import datetime

import click
import flask
import flask.cli
import IPython


@click.command("shell-plus")
@flask.cli.with_appcontext
def shell_plus():
    db_models = {}

    user_namespace = {
        # App contexts
        "app": flask.current_app,
        # DB Models
        **db_models,
        # Some useful shortcut variables
        "today": datetime.date.today,
    }

    IPython.embed(user_ns=user_namespace)
