import flask
import os
import werkzeug.middleware.proxy_fix as proxy_fix

import app.config as config


def create_app():
    app = flask.Flask(__name__,
                      instance_relative_config=True,
                      template_folder='static/template')
    runable_app = app

    environment = os.environ.get('FLASK_ENV', 'production')
    app.config.from_object(config.config_by_name[environment])

    if app.config.get('SERVER_IS_ON_PROXY'):
        app.wsgi_app = proxy_fix.ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    with app.app_context():
        import app.database as db
        runable_app = db.init_app(app)

        import app.api as api
        runable_app = api.init_app(runable_app)

        import app.admin as admin
        runable_app = admin.init_app(runable_app)

        import app.common.cli_tools as cli_tools
        runable_app = cli_tools.init_app(runable_app)

        import app.plugin as plugin
        runable_app = plugin.init_app(runable_app)

    return runable_app


if __name__ == '__main__':
    app = create_app()
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 8000)))
