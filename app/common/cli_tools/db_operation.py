import click
import flask
import flask.cli

import app.database


@click.command('drop-db')
@flask.cli.with_appcontext
def drop_db():
    try:
        if flask.current_app.config.get('RESTAPI_VERSION', 'prod') != 'dev':
            print('Cannot drop DB: RESTAPI_VERSION is not \'dev\'')
            return

        app.database.db.drop_all()
        print('Successfully dropped DB')
    except Exception:
        print('Error raised while dropping DB')
