import click
import flask
import flask.cli
import pathlib as pt

import app.database as db_module

db = db_module.db


@click.command('draw-db-erd')
@flask.cli.with_appcontext
def draw_db_erd():
    try:
        restapi_version = flask.current_app.config.get('RESTAPI_VERSION', 'prod')
        if restapi_version != 'dev':
            print('Cannot draw ERD of DB: RESTAPI_VERSION is not \'dev\'')
            return

        import codecs
        import sadisplay

        desc = sadisplay.describe([table_data[1] for table_data in db.metadata.tables.items()])

        with codecs.open(pt.Path(f'docs/{restapi_version}_db.dot'), 'w', encoding='utf-8') as f:
            f.write(sadisplay.dot(desc))

        print('Successfully drew ERD of service DB')
    except Exception:
        print('Error raised while drawing ERD of DB')
