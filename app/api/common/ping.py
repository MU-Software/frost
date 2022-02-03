import flask.views

import app.api.helper_class as api_class
from app.api.response_case import CommonResponseCase


class PingRoute(flask.views.MethodView, api_class.MethodViewMixin):
    def get(self):
        '''
        description: Ping-Pong
        responses:
            - ping_success
        '''
        return CommonResponseCase.ping_success.create_response()


resource_route = {
    '/ping': PingRoute
}
