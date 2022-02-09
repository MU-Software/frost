import flask
import flask_cors
import os

# I had to get these values from env,
# because We can initialize these values from flask config only on app context,
# and some modules already got these values before initialization.
restapi_version: str = os.environ.get('RESTAPI_VERSION')
server_name: str = os.environ.get('SERVER_NAME')

# This import is needed to prevent partially initialized ImportError
import app.api.helper_class as helper_class  # noqa


# Register views and handlers to app
def init_app(app: flask.Flask):
    global restapi_version
    restapi_version = app.config.get('RESTAPI_VERSION')
    app.url_map.strict_slashes = False

    allowed_origins: list = [f'https://{app.config.get("SERVER_NAME")}']
    local_client_port = app.config.get('LOCAL_DEV_CLIENT_PORT')
    if restapi_version == 'dev' and local_client_port:
        allowed_origins.append(f'http://localhost:{local_client_port}')
        allowed_origins.append(f'http://127.0.0.1:{local_client_port}')

    flask_cors.CORS(app, resources={
        r'*': {
            'origins': allowed_origins,
            'supports_credentials': True,
        }})

    import app.api.request_handler as req_handler  # noqa
    req_handler.register_request_handler(app)
    if app.config.get('DEBUG', False):
        import app.api.debug as debug_route
        debug_route.init_app(app)

    resource_routes: dict = {}

    import app.api.common.ping as route_ping  # noqa
    resource_routes.update(route_ping.resource_route)
    # Enable file-upload related routes when FILE_MANAGEMENT_ROUTE_ENABLE is True
    if app.config.get('FILE_MANAGEMENT_ROUTE_ENABLE', False):
        import app.api.common.file_manage as route_filemgr
        resource_routes.update(route_filemgr.resource_route)
    # Disable account related routes only when ACCOUNT_ROUTE_ENABLE is False
    if app.config.get('ACCOUNT_ROUTE_ENABLE', True):
        import app.api.account as route_account  # noqa
        resource_routes.update(route_account.resource_route)

    import app.api.project_route as project_route  # noqa
    resource_routes.update(project_route.project_resource_routes)

    for path, route_model in resource_routes.items():
        view_name: str = ''
        view_func = None
        defaults: dict = dict()
        if type(route_model) == dict:
            view_name = route_model['view_func'].__name__
            view_func = route_model['view_func'].as_view(view_name)
            base_path = route_model['base_path']
            defaults = route_model['defaults']
            app.add_url_rule('/api/' + restapi_version + path, view_func=view_func)
            app.add_url_rule('/api/' + restapi_version + base_path, view_func=view_func, defaults=defaults)
        elif type(route_model) == flask.views.MethodViewType:
            view_name = route_model.__name__
            view_func = route_model.as_view(view_name)
            app.add_url_rule('/api/' + restapi_version + path, view_func=view_func, defaults=defaults)

    # init_app must return app
    return app
