import copy
import dataclasses
import datetime
import enum
import flask
import functools
import inspect
import json
import jwt.exceptions
import typing
import unicodedata
import werkzeug.datastructures as wz_dt
import yaml

BASE_TYPE = typing.Type[typing.Union[str, bool, int, float, list, dict]]
openapi_type_def: dict[BASE_TYPE, str] = {
    str: 'string',
    bool: 'boolean',
    int: 'integer',
    float: 'number',
    list: 'array',
    dict: 'object',

    # Below will be automatically converted by jsonify
    datetime.datetime: 'string'
}
openapi_type_def_inverse: dict[str, BASE_TYPE] = {
    'string': str,
    'boolean': bool,
    'integer': int,
    'number': float,
    'array': list,
    'object': dict,
}
http_all_method = [
    'get', 'head', 'post', 'put',
    'delete', 'connect', 'options',
    'trace', 'patch']
ResponseType = tuple[typing.Any, int, tuple[tuple[str, str]]]


def recursive_dict_to_openapi_obj(in_dict: dict):
    result_dict: dict = dict()
    for k, v in in_dict.items():
        result_dict[k] = {'type': openapi_type_def[type(v)], }
        if v:
            if type(v) == dict:
                result_dict[k]['properties'] = recursive_dict_to_openapi_obj(v)
            elif type(v) == list:
                result_dict[k]['items'] = {'type': openapi_type_def[type(v[0])], }
                if type(v[0]) == dict:
                    result_dict[k]['properties'] = recursive_dict_to_openapi_obj(v[0])
            else:
                if type(v) is datetime.datetime:
                    result_dict[k]['enum'] = [v.strftime("%a, %d %b %Y %H:%M:%S GMT"), ]
                else:
                    result_dict[k]['enum'] = [v, ]

    return result_dict


class AutoRegisterClass:
    _subclasses = list()

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, '_base_class') or not cls._base_class:
            raise ValueError('_base_class must be set')

        # Attributes will be shared with parent classes while inheriting them,
        # so _subclasses attribute must be cleared when new class is created.
        cls._subclasses = list()

        for base_cls in cls.__bases__:
            if base_cls.__name__ == cls._base_class:
                base_cls._subclasses.append(cls)


# Make request form
def create_response(
        success: bool = True,
        code: int = 200,
        sub_code: str = '',
        message: str = '',
        data: dict = {},
        header: tuple = (('', ''),),
        ):

    # Although we can guess whether request is success or not in status code,
    # the reason why we use success field is because of redirection(302).
    response = {
        'success': success,
        'code': code,
        'sub_code': sub_code,
        'message': message,
        'data': data
    }

    server_name = flask.current_app.config.get('BACKEND_NAME', 'Backend Core')

    result_header = (
        *header,
        # We don't need to add Content-Type: application/json here
        # because flask.jsonify will add it.

        # Add CORS header
        ('Server', server_name),
    )

    return (flask.jsonify(response), code, result_header)


@dataclasses.dataclass
class Response:
    description: str = ''
    code: int = 500
    header: tuple[tuple[str, str]] = ()
    content_type: str = 'application/json'

    success: bool = ''
    public_sub_code: str = ''
    private_sub_code: str = ''

    # data can be JSON body or HTML format data.
    data: dict = dataclasses.field(default_factory=dict)
    # template should be a path to a html template file that can be found by flask.
    template_path: str = ''
    message: str = ''

    def to_openapi_obj(self):
        if self.content_type == 'application/json':
            return {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'enum': [self.success, ],
                    },
                    'code': {
                        'type': 'integer',
                        'enum': [self.code, ],
                    },
                    'sub_code': {
                        'type': 'string',
                        'enum': [self.public_sub_code, ],
                    },
                    'message': {
                        'type': 'string',
                    },
                    'data': {
                        'type': 'object',
                        'properties': recursive_dict_to_openapi_obj(self.data)
                    },
                },
            }
        elif self.content_type == 'text/html':
            if not self.template_path:
                raise Exception('template_path must be set when content_type is \'text/html\'')
            return {
                'type': 'string',
                'example': flask.render_template(self.template_path, **self.data),
            }

    def create_response(self,
                        code: int = None,
                        header: tuple[tuple[str]] = (),
                        data: dict = {},
                        message: typing.Optional[str] = None,
                        template_path: str = '',
                        content_type: str = '') -> ResponseType:

        resp_code: int = code if code is not None else self.code

        resp_header = [z for z in (header or self.header) if z[0] and z[1]]
        if resp_header:
            resp_header_name = [z[0] for z in resp_header]
            resp_header.append(('Access-Control-Expose-Headers', ', '.join(resp_header_name)))

        result_header = wz_dt.MultiDict((
            *resp_header,
            ('Server', flask.current_app.config.get('BACKEND_NAME', 'Backend Core')),
        ))

        resp_data = copy.deepcopy(data)
        resp_data.update(data)

        resp_template_path = template_path or self.template_path
        resp_content_type = content_type or self.content_type

        if resp_content_type == 'application/json':
            # TODO: Parse YAML file and get response message using public_sub_code
            response_body = {
                'success': self.success,
                'code': self.code,
                'sub_code': self.public_sub_code,
                'message': message or self.message,
                'data': resp_data
            }

            return (flask.jsonify(response_body), resp_code, result_header)
        elif resp_content_type == 'text/html':
            if not resp_template_path:
                raise Exception('template_path must be set when content_type is \'text/html\'')
            return (flask.render_template(resp_template_path, **resp_data), resp_code, result_header)
        else:
            raise NotImplementedError(f'Response type {resp_content_type} is not supported.')


class ResponseCaseCollector(AutoRegisterClass):
    _base_class = 'ResponseCaseCollector'


class ResponseDataModel:
    @classmethod
    def get_model_openapi_description(cls: typing.Type[dataclasses.dataclass]) -> dict:
        if not dataclasses.is_dataclass(cls):
            raise TypeError(f'Expected {str(type(cls))} as a dataclass instance, it\'s not.')

        result = dict()
        for name, field in cls.__dataclass_fields__.items():
            if type(field.type) is typing.GenericAlias:
                field.type = type(field.type())

            if field.type not in openapi_type_def:
                raise TypeError('Model field type must be one of these types, not {str(type(field.type))}'
                                '(str, bool, int, float, list, dict)')

            if field.type is dict and field.default_factory not in (dataclasses.MISSING, dataclasses._MISSING_TYPE):
                result[name] = field.default_factory()
            elif field.type is datetime.datetime:
                result[name] = datetime.datetime.now()
            elif field.default not in (dataclasses.MISSING, dataclasses._MISSING_TYPE):
                result[name] = field.default
            else:
                result[name] = field.type()

        return result


from app.api.response_case import CommonResponseCase  # noqa


class MethodViewMixin(AutoRegisterClass):
    _base_class = 'MethodViewMixin'
    __access_control_expose_headers_cache__: set[str] | None = None

    def options(self, *args, **kwargs):
        result_header = []

        all_mtd_name = inspect.getmembers(self, predicate=inspect.ismethod)
        http_mtd_name = [z[0] for z in all_mtd_name if z[0] in http_all_method]  # z[1] is method itself
        result_header.append(('Allow', ', '.join(http_mtd_name)))

        # Try to parse docstring and calculate Access-Control-Expose-Headers.
        # If we successfully calculated this, then we'll cache it for the further use.
        if self.__access_control_expose_headers_cache__ is None:
            self.__access_control_expose_headers_cache__ = set()

            http_mtd_method = [getattr(self, z) for z in http_mtd_name]
            http_mtd_docstring: list[str] = [getattr(z, '__doc__') for z in http_mtd_method
                                             if hasattr(z, '__doc__')]
            http_mtd_resp_cases_name = sum([yaml.safe_load(z).get('responses', None) for z in http_mtd_docstring
                                            if z], [])

            # FIXME: Cache this so that we don't need to calculate on every first OPTION request.
            response_cases: dict[str, Response] = dict()
            for response_case_collection in ResponseCaseCollector._subclasses:
                response_cases.update({k: v for k, v in response_case_collection.__dict__.items()
                                      if not k.startswith('_')})

            # Now we can collect possible header responses on possible responses.
            http_mtd_header_case_tuples = [response_cases[z].header for z in http_mtd_resp_cases_name]
            for header_cases in http_mtd_header_case_tuples:
                for header_case in header_cases:
                    self.__access_control_expose_headers_cache__.add(header_case[0])

        if self.__access_control_expose_headers_cache__:
            result_header.append(
                ('Access-Control-Expose-Headers', ', '.join(self.__access_control_expose_headers_cache__)))

        return CommonResponseCase.http_ok.create_response(header=result_header)


class AuthType(enum.Enum):
    Bearer = enum.auto()
    RefreshToken = enum.auto()


def json_list_filter(in_list: list, filter_empty_value: bool = True) -> list:
    result_list: list = list()

    for element in in_list:
        if type(element) is str:
            res_value = unicodedata.normalize('NFC', element).strip()
            if filter_empty_value and not res_value:
                continue
            result_list.append(res_value)
        elif type(element) in (int, float):
            result_list.append(element)
        elif type(element) is dict:
            res_value = json_dict_filter(element)
            if filter_empty_value and not res_value:
                continue
            result_list.append(res_value)
        elif type(element) is list:
            res_value = json_list_filter(element)
            if filter_empty_value and not res_value:
                continue
            result_list.append(res_value)
        elif type(element) is bool:
            result_list.append(element)
        elif element is None:
            if filter_empty_value:
                continue
            result_list.append(None)
        else:
            raise Exception('This is not a valid list of parsed json.')

    return result_list


def json_dict_filter(in_dict: dict, filter_empty_value: bool = True) -> dict:
    if not in_dict:
        return dict()

    result_dict: dict = dict()
    # Check value types and filter a type
    for k, v in in_dict.items():
        # key must be a string
        res_key: str = unicodedata.normalize('NFC', k).strip()
        if not res_key:
            continue

        res_value = None
        # value can be a string, number, object(dict), array(list), boolean(bool), or null(None)
        # match case please Python 3.10
        if type(v) is str:
            res_value = unicodedata.normalize('NFC', v).strip()
            if filter_empty_value and not res_value:
                continue
        elif type(v) in (int, float):
            res_value = v
        elif type(v) is dict:
            res_value = json_dict_filter(v, filter_empty_value)
            if filter_empty_value and not res_value:
                continue
        elif type(v) is list:
            res_value = json_list_filter(v, filter_empty_value)
            if filter_empty_value and not res_value:
                continue
        elif type(v) is bool:
            res_value = v
        elif v is None:
            res_value = None
            if filter_empty_value:
                continue
        else:
            raise Exception('This is not a valid dict of parsed json.')

        result_dict[res_key] = res_value

    return result_dict


def dict_type_check(type_def: dict[str, dict[str, str]],
                    data: dict[str, typing.Any]) -> typing.Optional[tuple[str, str, str]]:
    type_def_rtypes = {k: openapi_type_def_inverse[v['type']] for k, v in type_def.items()}
    data_for_iter = copy.deepcopy(data)

    for data_k, data_v in data_for_iter.items():
        expected_type = type_def_rtypes.get(data_k, None)

        if not expected_type:
            return (data_k, 'UNKNOWN', 'UNKNOWN')

        if expected_type is str:
            if not isinstance(data_v, str):
                data[data_k] = str(data_v)

        elif not isinstance(data_v, expected_type):
            if isinstance(data_v, str):
                # If field's type is str, then at least we can try conversion.
                try:
                    data_v_parsed = json.loads(data_v)
                    if expected_type in (int, float) and isinstance(data_v_parsed, (int, float)):
                        data[data_k] = expected_type(data_v_parsed)
                        continue
                    elif isinstance(data_v_parsed, expected_type):
                        data[data_k] = expected_type(data_v_parsed)
                        continue
                except Exception:
                    pass

            # Field name / Expected type / Type we got
            expected_type_openapi_str = openapi_type_def[expected_type]
            type_we_got = openapi_type_def.get(type(data_v), 'UNKNOWN')
            return (data_k, expected_type_openapi_str, type_we_got)

    return None


class RequestHeader:
    def __init__(self,
                 required_fields: typing.Optional[dict[str, dict[str, str]]] = None,
                 optional_fields: typing.Optional[dict[str, dict[str, str]]] = None,
                 auth: typing.Optional[dict[AuthType, bool]] = None):
        self.req_header: dict = dict()
        self.required_fields: dict[str, dict[str, str]] = required_fields or {}
        self.optional_fields: dict[str, dict[str, str]] = optional_fields or {}
        self.auth: dict[AuthType, bool] = auth or {}

        self.fields: dict[str, dict[str, str]] = copy.deepcopy(self.required_fields)
        self.fields.update(self.optional_fields)

        if AuthType.Bearer in self.auth:
            if self.auth[AuthType.Bearer]:
                self.required_fields['Authorization'] = {'type': 'string', }
                self.required_fields['X-Csrf-Token'] = {'type': 'string', }
            else:
                self.optional_fields['Authorization'] = {'type': 'string', }
                self.optional_fields['X-Csrf-Token'] = {'type': 'string', }

    def __call__(self, func: typing.Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Filter for empty keys and values
                self.req_header = json_dict_filter(flask.request.headers, True)

                # Check if all required fields are in
                if (not all([z in self.req_header.keys() for z in self.required_fields])):
                    return CommonResponseCase.header_required_omitted.create_response(
                        data={'lacks': [z for z in self.required_fields if z not in self.req_header], })

                # Remove every field not in required and optional fields
                self.req_header = {k: self.req_header[k] for k in self.req_header
                                   if k in list(self.required_fields.keys()) + list(self.optional_fields.keys())}
                if self.required_fields and not self.req_header:
                    return CommonResponseCase.header_required_omitted.create_response(
                        data={'lacks': list(self.required_fields.keys()), })

                if self.required_fields or self.optional_fields:
                    kwargs['req_header'] = self.req_header
            except Exception:
                return CommonResponseCase.header_invalid.create_response()

            import app.api.account.response_case as account_resp_case  # noqa
            import app.database.jwt as jwt_module  # noqa

            # Check Authorization
            if self.auth:
                for auth, required in self.auth.items():
                    # We need match-case syntax which is introduced on Python 3.10
                    if auth == AuthType.Bearer:
                        csrf_token = self.req_header.get('X-Csrf-Token', None)
                        if required and not csrf_token:
                            return account_resp_case.AccountResponseCase.access_token_invalid.create_response()

                        try:
                            access_token_bearer = flask.request.headers.get('Authorization', '').replace('Bearer ', '')
                            access_token = jwt_module.AccessToken.from_token(
                                access_token_bearer,
                                flask.current_app.config.get('SECRET_KEY')+csrf_token)
                            kwargs['access_token'] = access_token
                        except jwt.exceptions.ExpiredSignatureError:
                            # AccessToken Expired error must be raised when bearer auth is softly required,
                            # so that client can re-request after refreshing AccessToken
                            return account_resp_case.AccountResponseCase.access_token_expired.create_response()
                        except Exception:
                            if required:
                                return account_resp_case.AccountResponseCase.access_token_invalid.create_response()
                        finally:
                            if not required and 'access_token' not in kwargs:
                                kwargs['access_token'] = None

                    elif auth == AuthType.RefreshToken:
                        refresh_token_cookie = flask.request.cookies.get('refresh_token', None)
                        if not refresh_token_cookie:
                            if required:
                                return account_resp_case.AccountResponseCase.user_not_signed_in.create_response()

                        try:
                            refresh_token = jwt_module.RefreshToken.from_token(
                                refresh_token_cookie,
                                flask.current_app.config.get('SECRET_KEY'))
                            kwargs['refresh_token'] = refresh_token
                        except jwt.exceptions.ExpiredSignatureError:
                            if required:
                                return account_resp_case.AccountResponseCase.refresh_token_expired.create_response()
                        except Exception:
                            if required:
                                return account_resp_case.AccountResponseCase.refresh_token_invalid.create_response()
                        finally:
                            if not required and 'refresh_token' not in kwargs:
                                kwargs['refresh_token'] = None
            return func(*args, **kwargs)

        # Parse docstring and inject parameter data
        if doc_str := inspect.getdoc(func):
            doc_data: dict = yaml.safe_load(doc_str)

            if self.auth:
                if 'security' not in doc_data:
                    doc_data['security'] = list()

                for auth in self.auth:
                    doc_data['security'].append({auth.name + 'Auth': list(), })

            if 'parameters' not in doc_data:
                doc_data['parameters'] = []

            parm_collector: list = list()
            for k, v in self.required_fields.items():
                # Check if same named field data is already in parm_collector
                if [z for z in parm_collector if type(z) is dict and z['name'] == k]:
                    continue

                field_data = {
                    'in': 'header',
                    'name': k,
                    'required': True
                }
                if 'description' in v:
                    field_data['description'] = v['description']

                if 'type' in v:
                    field_data['schema'] = {'type': v['type'], }

                parm_collector.append(field_data)

            for k, v in self.optional_fields.items():
                # Check if same named field data is already in parm_collector
                if [z for z in parm_collector if type(z) is dict and z['name'] == k]:
                    continue

                field_data = {
                    'in': 'header',
                    'name': k,
                }
                if 'description' in v:
                    field_data['description'] = v['description']

                if 'type' in v:
                    field_data['schema'] = {'type': v['type'], }

                parm_collector.append(field_data)

            doc_data['parameters'] += parm_collector

            if self.required_fields:
                if not doc_data['responses']:
                    doc_data['responses'] = list()
                doc_data['responses'] += [
                    'header_invalid',
                    'header_required_omitted']

            if self.auth:
                if AuthType.Bearer in self.auth:
                    if self.auth[AuthType.Bearer]:
                        doc_data['responses'] += [
                            'access_token_expired',
                            'access_token_invalid',
                        ]
                    else:
                        # AccessToken Expired error must be raised when bearer auth is softly required,
                        # so that client can re-request after refreshing AccessToken
                        doc_data['responses'] += [
                            'access_token_expired',
                        ]

                if AuthType.RefreshToken in self.auth and self.auth[AuthType.RefreshToken]:
                    doc_data['responses'] += [
                        'user_not_signed_in',
                        'refresh_token_expired',
                        'refresh_token_invalid',
                    ]

            func.__doc__ = yaml.safe_dump(doc_data)
            wrapper.__doc__ = yaml.safe_dump(doc_data)

        return wrapper


class RequestQuery:
    def __init__(self,
                 required_fields: typing.Optional[dict[str, dict[str, str]]] = None,
                 optional_fields: typing.Optional[dict[str, dict[str, str]]] = None):
        self.req_query: dict = dict()
        self.required_fields: dict[str, dict[str, str]] = required_fields or {}
        self.optional_fields: dict[str, dict[str, str]] = optional_fields or {}

        self.fields: dict[str, dict[str, str]] = copy.deepcopy(self.required_fields)
        self.fields.update(self.optional_fields)

    def __call__(self, func: typing.Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Filter for empty keys and values
                self.req_query = json_dict_filter(flask.request.args.copy(), True)

                # Check if all required fields are in
                if (not all([z in self.req_query.keys() for z in self.required_fields])):
                    return CommonResponseCase.path_required_omitted.create_response(
                        data={'lacks': [z for z in self.required_fields if z not in self.req_query], })

                # Remove every field not in required and optional fields
                self.req_query = {k: self.req_query[k] for k in self.req_query
                                  if k in list(self.required_fields.keys()) + list(self.optional_fields.keys())}

                # Remove every field not in required and optional fields
                self.req_query = {k: self.req_query[k] for k in self.req_query
                                  if k in list(self.required_fields.keys()) + list(self.optional_fields.keys())}
                if self.required_fields and not self.req_query:
                    return CommonResponseCase.path_required_omitted.create_response(
                        data={'lacks': list(self.required_fields.keys()), })

                if self.required_fields or self.optional_fields:
                    kwargs['req_query'] = self.req_query
            except Exception:
                return CommonResponseCase.body_invalid.create_response()

            return func(*args, **kwargs)

        # Parse docstring and inject parameter data
        if doc_str := inspect.getdoc(func):
            doc_data: dict = yaml.safe_load(doc_str)

            if 'parameters' not in doc_data:
                doc_data['parameters'] = []

            parm_collector: list = list()
            for k, v in self.required_fields.items():
                field_data = {
                    'in': 'query',
                    'name': k,
                    'required': True
                }
                if 'description' in v:
                    field_data['description'] = v['description']

                if 'type' in v:
                    field_data['schema'] = {'type': v['type'], }

                parm_collector.append(field_data)
            for k, v in self.optional_fields.items():
                field_data = {
                    'in': 'query',
                    'name': k,
                }
                if 'description' in v:
                    field_data['description'] = v['description']

                if 'type' in v:
                    field_data['schema'] = {'type': v['type'], }

                parm_collector.append(field_data)
            doc_data['parameters'] += parm_collector

            if self.required_fields:
                if not doc_data['responses']:
                    doc_data['responses'] = list()
                doc_data['responses'] += ['path_required_omitted', ]

            func.__doc__ = yaml.safe_dump(doc_data)
            wrapper.__doc__ = yaml.safe_dump(doc_data)

        return wrapper


class RequestBody:
    def __init__(self,
                 required_fields: typing.Optional[dict[str, dict[str, str]]] = None,
                 optional_fields: typing.Optional[dict[str, dict[str, str]]] = None):
        self.req_body: dict = dict()
        self.required_fields: dict[str, dict[str, str]] = required_fields or {}
        self.optional_fields: dict[str, dict[str, str]] = optional_fields or {}

        self.fields: dict[str, dict[str, str]] = copy.deepcopy(self.required_fields)
        self.fields.update(self.optional_fields)

    def __call__(self, func: typing.Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Filter for empty keys and values
                self.req_body = None
                try:
                    self.req_body = json_dict_filter(flask.request.get_json(force=True), True)
                except Exception:
                    # Try to get body data from FormData
                    self.req_body = json_dict_filter(flask.request.form.to_dict(flat=True), True)
                if self.req_body is None:
                    raise Exception('Getting body data from request failed')

                # Check if all required fields are in
                if (not all([z in self.req_body.keys() for z in self.required_fields])):
                    return CommonResponseCase.body_required_omitted.create_response(
                        data={'lacks': [z for z in self.required_fields if z not in self.req_body], }, )

                # Remove every field not in required and optional fields
                self.req_body = {k: self.req_body[k] for k in self.req_body
                                 if k in list(self.required_fields.keys()) + list(self.optional_fields.keys())}
                if self.required_fields and not self.req_body:
                    return CommonResponseCase.body_empty.create_response()

                # Type check the values
                req_type_check_result = dict_type_check(self.fields, self.req_body)
                if req_type_check_result:
                    field_name, expected_type, type_we_got = req_type_check_result
                    error_msg = f'Expected type `{expected_type}`, but got `{type_we_got}`'
                    return CommonResponseCase.body_bad_semantics.create_response(
                        message=error_msg,
                        data={'bad_semantics': [{'field': field_name, 'reason': error_msg, }, ], }, )

            except Exception:
                return CommonResponseCase.body_invalid.create_response()

            kwargs['req_body'] = self.req_body
            return func(*args, **kwargs)

        # Parse docstring and inject requestBody data
        if doc_str := inspect.getdoc(func):
            doc_data: dict = yaml.safe_load(doc_str)
            if 'requestBody' not in doc_data:
                doc_data['requestBody'] = {
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {},
                                'required': [],
                            }
                        }
                    }
                }

            properties: dict = dict()
            required: list = list()
            for k, v in self.required_fields.items():
                properties[k] = v
                required.append(k)
            for k, v in self.optional_fields.items():
                properties[k] = v

            doc_data['requestBody']['content']['application/json']['schema']['properties'].update(properties)
            doc_data['requestBody']['content']['application/json']['schema']['required'] += required

            if not doc_data['requestBody']['content']['application/json']['schema']['required']:
                doc_data['requestBody']['content']['application/json']['schema'].pop('required')

            if self.required_fields:
                if not doc_data['responses']:
                    doc_data['responses'] = list()
                doc_data['responses'] += [
                    'body_required_omitted',
                    'body_empty',
                    'body_invalid']

            func.__doc__ = yaml.safe_dump(doc_data)
            wrapper.__doc__ = yaml.safe_dump(doc_data)

        return wrapper
