import flask

import app.common.cli_tools.db_erd_draw as db_erd_draw
import app.common.cli_tools.db_operation as db_operation
import app.common.cli_tools.openapi_support as openapi_support
import app.common.cli_tools.shell_plus as shell_plus


def init_app(app: flask.Flask):
    app.cli.add_command(openapi_support.create_openapi_doc)
    app.cli.add_command(db_operation.drop_db)
    app.cli.add_command(db_erd_draw.draw_db_erd)
    app.cli.add_command(shell_plus.shell_plus)

    # init_app must return app
    return app
