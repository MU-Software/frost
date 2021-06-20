import flask
import os

restapi_version = os.environ.get('RESTAPI_VERSION')


def init_app(app: flask.Flask):
    @app.route(f'/api/{restapi_version}/debug/<path:path>')
    def static_route(path):
        return flask.send_from_directory('static/debug', path)
