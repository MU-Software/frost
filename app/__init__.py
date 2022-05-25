import flask
import logging
import os
import werkzeug.middleware.proxy_fix as proxy_fix

import app.config as config

IS_GUNICORN = 'gunicorn' in os.environ.get('SERVER_SOFTWARE', '')

LOG_NAME_TO_LEVEL = {
    'CRITICAL': logging.CRITICAL,
    'FATAL': logging.FATAL,
    'ERROR': logging.ERROR,
    'WARN': logging.WARNING,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
    'NOTSET': logging.NOTSET,
}


def create_app(**kwargs):
    if os.environ.get('LOG_FILE_ENABLE', False) == 'true':
        log_file_name = os.environ.get('LOG_FILE_NAME', os.environ.get('SERVER_NAME', 'frost_log') + '.log')
        log_level = LOG_NAME_TO_LEVEL.get(os.environ.get('LOG_FILE_LEVEL', '').upper(), None)
        if not log_level:
            log_level = logging.DEBUG if os.environ.get('RESTAPI_VERSION', '') == 'dev' else logging.WARNING

        logging.basicConfig(filename=log_file_name, level=log_level, )

    app = flask.Flask(__name__,
                      instance_relative_config=True,
                      template_folder='static/template')
    runable_app = app

    environment = os.environ.get('FLASK_ENV', 'production')
    app.config.from_object(config.config_by_name[environment])

    if app.config.get('SERVER_IS_ON_PROXY'):
        app.wsgi_app = proxy_fix.ProxyFix(
            app.wsgi_app,
            x_for=app.config.get('X_FOR_LEVEL'),
            x_proto=app.config.get('X_PROTO_LEVEL'),
            x_host=app.config.get('X_HOST_LEVEL'),
            x_port=app.config.get('X_PORT_LEVEL'),
            x_prefix=app.config.get('X_PREFIX_LEVEL'))

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

    if kwargs.get('return_plugin_app', False):
        return runable_app
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', 8000)))
elif IS_GUNICORN:
    gunicorn_app = create_app()
