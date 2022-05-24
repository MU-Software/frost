# -*- coding: UTF-8 -*-
import datetime
import email
import enum
import flask
import hashlib
import json
import math
import os
import random
import socket
import string
import sqlalchemy as sql
import sqlalchemy.ext.declarative as sqldec
import time
import traceback
import typing
import unicodedata
import werkzeug

# ---------- Type hint related variables, NEVER USE OUTSIDE OF THE MODULES! ----------
T = typing.TypeVar('T')

# ---------- Check and Normalize strings ----------
char_printable: str = string.ascii_letters + string.digits
char_printable     += string.punctuation  # noqa

char_urlsafe: str = string.ascii_letters + string.digits
char_urlsafe     += '-_'  # noqa

char_useridsafe: str = string.ascii_letters + string.digits


def normalize(s: str) -> str:
    return unicodedata.normalize('NFC', s)


def char_type(s):
    c_type = {
        'lower': string.ascii_lowercase,
        'upper': string.ascii_uppercase,
        'digit': string.digits,
        'punct': string.punctuation}
    for key, value in c_type.items():
        if s in value:
            return key
    return None


def get_str_char_types(target_str):
    str_char_type = list()
    for target_char in target_str:
        str_char_type.append(char_type(target_char))
    return list(set(str_char_type))


def is_email(s: str) -> bool:
    try:
        parsed_email = email.utils.parseaddr(s)[1]
        if parsed_email:
            if len(parsed_email.split('@')[1].split('.')) >= 2:
                return True
    except Exception:
        return False
    return False


def is_printable(s: str) -> bool:
    for c in s:
        if c not in char_printable:
            return False
    return True


def is_urlsafe(s: str) -> bool:
    for c in s:
        if c not in char_urlsafe:
            return False
    return True


def is_useridsafe(s: str) -> str:
    if 4 > len(s):
        return 'TOO_SHORT'
    if len(s) > 48:
        return 'TOO_LONG'

    for c in s:
        if c not in char_useridsafe:
            return 'FORBIDDEN_CHAR'

    return ''


def is_passwordsafe(s: str,
                    min_char_type_num: int = 2,
                    min_len: int = 8,
                    max_len: int = 1024) -> str:
    # Returnable case:
    #   '': OK.
    #   'TOO_LONG': Password is too long.
    #   'TOO_SHORT': Password is too short.
    #   'NEED_MORE_CHAR_TYPE': Password must have more char type.
    #   'FORBIDDEN_CHAR': Password has forbidden char type.
    if len(s) < min_len:
        return 'TOO_SHORT'
    if max_len < len(s):
        return 'TOO_LONG'

    s_char_type = get_str_char_types(s)
    if len(s_char_type) < min_char_type_num:
        return 'NEED_MORE_CHAR_TYPE'

    if not all(s_char_type):
        return 'FORBIDDEN_CHAR'

    return ''


# ---------- Standard statement to function ----------
def raise_(e) -> None:
    raise e


def get_traceback_msg(err):
    # FUTURE: We can pass the exception object only on Python 3.10
    return ''.join(traceback.format_exception(err, value=err, tb=err.__traceback__))


# ---------- Elegant Pairing ----------
# http://szudzik.com/ElegantPairing.pdf
def elegant_pair(x, y) -> int:
    return x * x + x + y if x >= y else y * y + x


def elegant_unpair(z) -> tuple:
    sqrtz = math.floor(math.sqrt(z))
    sqz   = sqrtz * sqrtz  # noqa
    return (sqrtz, z - sqz - sqrtz) if (z - sqz) >= sqrtz\
           else (z - sqz, sqrtz)  # noqa


# ---------- Hash calculation function ----------
def fileobj_md5(fp) -> str:
    hash_md5 = hashlib.md5()
    fp.seek(0)
    for chunk in iter(lambda: fp.read(4096), b""):
        hash_md5.update(chunk)
    fp.seek(0)
    return hash_md5.hexdigest()


def file_md5(fname: os.PathLike) -> str:
    return fileobj_md5(open(fname, 'rb'))


# ---------- Custom Exceptions ----------
def BackendException(code=500, data='',
                     backend_log=None, client_header=[],
                     description='Unexpected error happened. '
                                 'Contect to Administrator.',
                     json_prettier=None):
    # custom_headers should be list,
    # because we cannot make multiple items with same key in dict,
    # and setting Set-Cookie header multiple times is the case.
    if not isinstance(client_header, list):
        raise ValueError('client_header type must be list')

    # Enable JSON prettier when app is debug mode.
    json_prettier = 4 if flask.current_app.config.get('DEBUG', None) else None

    custom_headers = [('Content-Type', 'application/json; charset=utf-8'), ]
    if client_header:
        custom_headers += client_header

    body = {
        'IsSuccess': False,
        'status': code,
        'message': description,
        'data': data,
    }
    body_json = json.dumps(body, indent=json_prettier)

    err = werkzeug.exceptions.HTTPException()

    err.code = code
    err.description = description
    err.response = werkzeug.wrappers.response.Response(
                        body_json, code, custom_headers)

    err.get_body = lambda self, environ=None: body_json
    err.get_headers = lambda self, environ=None: custom_headers

    setattr(err, 'backend_log', backend_log)
    setattr(err, 'frost_exception', True)

    return err


# ---------- Timezone ----------
UTC = datetime.timezone.utc
KST = datetime.timezone(datetime.timedelta(hours=9))


# ---------- Time Calculator ----------
utc_desc   = lambda a, syntax='%Y/%m/%d %H:%M:%S': time.strftime(syntax, time.gmtime(a))  # noqa

date_to_time: typing.Callable[[int, ], int] = lambda x: x * 24 * 60 * 60  # noqa
hour_to_time: typing.Callable[[int, ], int] = lambda x: x      * 60 * 60  # noqa
update_rate: typing.Callable[[int, ], int] = date_to_time(2) - hour_to_time(1)  # noqa

as_utctime: typing.Callable[[datetime.datetime, ], datetime.datetime] = lambda x: x.replace(tzinfo=UTC)  # noqa
as_timestamp: typing.Callable[[datetime.datetime, ], int] = lambda x: as_utctime(x).timestamp()  # noqa


# ---------- Cookie Handler ----------
def cookie_creator(
        name: str, data: str, path: str = '/', domain: str = None,
        expires: str = None, maxage: int = None, never_expire: bool = False,
        samesite: str = 'strict', secure: bool = True, httponly: bool = True) -> str:
    if not any([expires, maxage, never_expire]):
        err_msg = 'At least one of the expires, maxage, never_expire'\
                  'should be set.'
        raise ValueError(err_msg)

    if never_expire:
        expires = 'Sat, 19 Jan 2038 04:14:07 GMT'

    header_cookie = list()
    header_cookie.append(f'{name}={data}')
    header_cookie.append(f'path={path}')

    if expires:
        header_cookie.append(f'Expires={expires}')
    else:
        header_cookie.append(f'Max-Age={maxage}')

    if domain:
        header_cookie.append(f'Domain={domain}')
    if samesite:
        header_cookie.append(f'SameSite={samesite}')
    if secure:
        header_cookie.append('secure')
    if httponly:
        header_cookie.append('HttpOnly')

    return '; '.join(header_cookie)


def user_cookie(data: str, secure: bool = True) -> str:
    return cookie_creator(
        'userJWT', data, path='/',
        never_expire=True, secure=secure
    )


def delete_cookie(name: str, path: str = '/', domain: str = '',
                  secure: bool = True, samesite: str = 'strict', httponly: bool = True) -> str:
    return cookie_creator(
        name, 'DUMMY', path=path, domain=domain,
        secure=secure, samesite=samesite, httponly=httponly,
        expires='Thu, 01 Jan 1970 00:00:00 GMT',
    )


def cookie_datetime(dt_time: datetime.datetime) -> str:
    if type(dt_time) != datetime.datetime:
        raise TypeError(f'a datetime object is required (got type {str(type(dt_time))})')

    dt_time = dt_time.replace(tzinfo=UTC)
    return dt_time.strftime("%a, %d %b %Y %H:%M:%S GMT")


# ---------- Helper Function ----------
def isiterable(in_obj):
    try:
        iter(in_obj)
        return True
    except Exception:
        return False


def ignore_exception(IgnoreException: typing.Type[Exception] = Exception, DefaultVal: T = None):
    # from https://stackoverflow.com/a/2262424
    """ Decorator for ignoring exception from a function
    e.g.   @ignore_exception(DivideByZero)
    e.g.2. ignore_exception(DivideByZero)(Divide)(2/0)
    """
    def dec(function):
        def _dec(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except IgnoreException:
                return DefaultVal
        return _dec
    return dec


safe_int = ignore_exception(Exception, 0)(int)
safe_json_loads = ignore_exception(Exception, None)(json.loads)


def json_default(value):
    if isinstance(value, datetime.date):
        return value.strftime("%a, %d %b %Y %H:%M:%S GMT")
    raise TypeError('not JSON serializable')


# ---------- ETC ----------
pmmod_desc = lambda a: ''.join(y for x,y in zip([4&a,2&a,1&a], list('RWX')) if x)  # noqa


# ---------- Utility Classes ----------
class Singleton(type):  # Singleton metaclass
    '''
    from: https://stackoverflow.com/a/6798042/5702135
    usage:
        class Logger(metaclass=Singleton):
            pass
    '''
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Struct:
    def __init__(self, **entries):
        self.__dict__.update(entries)


class EnumAutoName(enum.Enum):
    def _generate_next_value_(name, start, count, last_values):
        return name


class hybridmethod:
    """
    This can make us to write classmethod and instancemethod with same name
    From https://stackoverflow.com/a/28238047
    """
    def __init__(self, fclass, finstance=None, doc=None):
        self.fclass = fclass
        self.finstance = finstance
        self.__doc__ = doc or fclass.__doc__
        # support use on abstract base classes
        self.__isabstractmethod__ = bool(
            getattr(fclass, '__isabstractmethod__', False)
        )

    def classmethod(self, fclass):
        return type(self)(fclass, self.finstance, None)

    def instancemethod(self, finstance):
        return type(self)(self.fclass, finstance, self.__doc__)

    def __get__(self, instance, cls):
        if instance is None or self.finstance is None:
            # either bound to the class, or no instance method available
            return self.fclass.__get__(cls, None)
        return self.finstance.__get__(instance, cls)


class class_or_instancemethod(classmethod):
    """
    This can make us to write classmethod and instancemethod on same method object.
    From https://stackoverflow.com/a/28238047
    """
    def __get__(self, instance, type_):
        descr_get = super().__get__ if instance is None else self.__func__.__get__
        return descr_get(instance, type_)


# ---------- SQLAlchemy helper Function ----------
def get_model_changes(model):
    """
    Return a dictionary containing changes made to the model since it was
    fetched from the database.

    The dictionary is of the form {'property_name': [old_value, new_value]}

    Example:
        user = get_user_by_id(420)
        >>> '<User id=402 email="business_email@gmail.com">'
        get_model_changes(user)
        >>> {}
        user.email = 'new_email@who-dis.biz'
        get_model_changes(user)
        >>> {'email': ['business_email@gmail.com', 'new_email@who-dis.biz']}

    FROM https://stackoverflow.com/a/56351576
    """
    state = sql.inspect(model)
    changes = {}

    for attr in state.attrs:
        hist = state.get_history(attr.key, True)

        if not hist.has_changes():
            continue

        old_value = hist.deleted[0] if hist.deleted else None
        new_value = hist.added[0] if hist.added else None
        changes[attr.key] = [old_value, new_value]

    return changes


def has_model_changed(model):
    """
    Return True if there are any unsaved changes on the model.
    """
    return bool(get_model_changes(model))


def create_dynamic_orm_table(
        base: sqldec.DeclarativeMeta,
        engine: sql.engine.base.Engine,
        class_name: str, table_name: str,
        columns: typing.Optional[list[str]] = None,
        mixins: tuple = ()):

    table_attrs: dict = {
        '__tablename__': table_name,
        '__table_args__': {
            'sqlite_autoincrement': True,
            'autoload': True,
            'autoload_with': engine,
        },
    }
    table_attrs.update(columns if columns else {})

    DynamicORMTable = type(class_name, (*mixins, base), table_attrs)
    return DynamicORMTable


# ---------- Extra tools ----------
def find_free_random_port(port: int = 24000, max_port: int = 34000) -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tried_ports = list()
    while True:
        if len(range(port, max_port)) == len(tried_ports):
            raise IOError('no free ports')

        port = random.randint(port, max_port)
        if port in tried_ports:
            continue

        try:
            sock.bind(('', port))
            sock.close()
            return port
        except OSError:
            continue
