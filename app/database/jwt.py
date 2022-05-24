import datetime
import flask
import inspect
import jwt
import jwt.exceptions
import redis
import secrets
import user_agents as ua
import user_agents.parsers as ua_parser
import typing

import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module

db = db_module.db
redis_db: redis.StrictRedis = db_module.redis_db
RedisKeyType = db_module.RedisKeyType

# Refresh token will expire after 61 days
refresh_token_valid_duration: datetime.timedelta = datetime.timedelta(days=61)
# Access token will expire after 1 hour
access_token_valid_duration: datetime.timedelta = datetime.timedelta(hours=1)
# Admin token will expire after 12 hours
admin_token_valid_duration: datetime.timedelta = datetime.timedelta(hours=12)

T = typing.TypeVar('T', bound='TokenBase')


class TokenBase:
    ALLOWED_CLAIM = ['api_ver', 'iss', 'exp', 'user', 'sub', 'jti', 'role', 'otp']

    # This will raise error when env var "RESTAPI_VERSION" not set.
    api_ver: str = flask.current_app.config.get('RESTAPI_VERSION')

    # Registered Claim
    iss: str = flask.current_app.config.get('SERVER_NAME')  # Token Issuer(Fixed)
    exp: datetime.datetime = None  # Expiration Unix Time
    sub: str = ''  # Token name
    jti: int = -1  # JWT token ID

    # We won't use public claim yet
    # domain: str = ''

    # Private Claim
    user: int = -1  # Audience, User, Token holder
    role: str = ''
    otp: str = ''
    # data: dict

    def is_admin(self):
        json_result = utils.safe_json_loads(self.role)
        if json_result and 'admin' in json_result:
            return True
        return False

    def create_token(self, key: str, algorithm: str = 'HS256') -> str:
        if not self.sub:
            raise jwt.exceptions.MissingRequiredClaimError('Subject not set in JWT class')
        if self.user and type(self.user) == int and self.user < 0:
            raise jwt.exceptions.MissingRequiredClaimError('Audience not set in JWT class')
        if self.jti and type(self.jti) == int and self.jti < 0:
            raise jwt.exceptions.MissingRequiredClaimError('Token ID not set in JWT class')

        current_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

        if type(self.exp) == int:
            token_exp_time = datetime.datetime.fromtimestamp(self.exp, utils.UTC)
        else:
            if self.exp:
                token_exp_time = self.exp.replace(tzinfo=utils.UTC)
            else:
                token_exp_time = None

        if (not token_exp_time) or (token_exp_time < current_time):
            raise jwt.exceptions.ExpiredSignatureError('Token has reached expiration time')

        result_payload = dict()
        attrs = inspect.getmembers(self, lambda o: not callable(o))

        for attr_name, attr_value in attrs:
            if attr_name in self.ALLOWED_CLAIM:
                result_payload[attr_name] = attr_value

        return jwt.encode(payload=result_payload, key=key, algorithm=algorithm)

    @classmethod
    def from_token(cls: typing.Type[T], jwt_input: str, key: str, algorithm: str = 'HS256') -> T:
        token_data = jwt.decode(jwt_input, key=key, algorithms=algorithm)

        current_api_ver: str = flask.current_app.config.get('RESTAPI_VERSION')
        if token_data.get('api_ver', '') != current_api_ver:
            raise jwt.exceptions.InvalidTokenError('Token api version mismatch')
        if token_data.get('sub', '') != cls.sub:
            raise jwt.exceptions.InvalidTokenError('Token sub mismatch')

        token_exp_time = token_data.get('exp', 0)
        if type(token_exp_time) == int:
            if not token_exp_time:
                raise jwt.exceptions.ExpiredSignatureError('No expiration date included')
            token_exp_time = datetime.datetime.fromtimestamp(token_exp_time, utils.UTC)
        elif type(token_exp_time) == datetime.datetime:
            token_exp_time = token_exp_time.replace(tzinfo=utils.UTC)
        else:
            raise jwt.exceptions.InvalidTokenError('Expiration date could not be parsed')

        if token_exp_time < datetime.datetime.utcnow().replace(tzinfo=utils.UTC):
            raise jwt.exceptions.ExpiredSignatureError('Token has reached expiration time')
        token_data['exp'] = token_exp_time

        if token_data.get('user') < 0:
            raise jwt.exceptions.InvalidTokenError(f'User UUID in token is {token_data.get("user")}')

        # Filter and rebuild token data so that only allowed claim is in token
        token_data = {k: token_data[k] for k in token_data if k in cls.ALLOWED_CLAIM}

        new_token = cls()
        new_token.__dict__.update(token_data)
        return new_token


class AccessToken(TokenBase):
    # Registered Claim
    sub: str = 'Access'

    _refresh_token: 'RefreshToken' = None

    def create_token(self, key: str, algorithm: str = 'HS256', exp_reset: bool = True) -> str:
        if not db.session.query(RefreshToken).filter(RefreshToken.jti == self.jti).first():
            raise Exception('Access Token could not be issued')

        new_token = super().create_token(key, algorithm=algorithm)

        # If new token safely issued, then remove revoked history
        redis_key = RedisKeyType.TOKEN_REVOKE.as_redis_key(self.jti)
        redis_result = redis_db.get(redis_key)
        if redis_result and redis_result == b'revoked':
            redis_db.delete(redis_key)

        return new_token

    @classmethod
    def from_token(cls, jwt_input: str, key: str, algorithm: str = 'HS256') -> 'AccessToken':
        parsed_token = super().from_token(jwt_input, key, algorithm)

        # Check if token's revoked
        redis_key = RedisKeyType.TOKEN_REVOKE.as_redis_key(parsed_token.jti)
        redis_result = redis_db.get(redis_key)
        if redis_result and redis_result == b'revoked':
            raise jwt.exceptions.InvalidTokenError('This token was revoked')

        return parsed_token

    @classmethod
    def from_refresh_token(cls, refresh_token: 'RefreshToken'):
        # Check refresh token exp
        current_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

        if type(refresh_token.exp) == int:
            token_exp_time = datetime.datetime.fromtimestamp(refresh_token.exp, utils.UTC)
        else:
            if refresh_token.exp:
                token_exp_time = refresh_token.exp.replace(tzinfo=utils.UTC)
            else:
                token_exp_time = None
        if (not token_exp_time) or (token_exp_time < current_time):
            raise jwt.exceptions.ExpiredSignatureError('Refresh token has reached expiration time')

        new_token = AccessToken()
        new_token._refresh_token = refresh_token
        new_token.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
        new_token.exp += access_token_valid_duration
        new_token.user = refresh_token.user
        # Access token's JTI must be same with Refresh token's.
        new_token.jti = refresh_token.jti
        # role field must be refreshed from TB_USER
        new_token.role = refresh_token.usertable.role

        return new_token


class RefreshToken(TokenBase, db.Model, db_module.DefaultModelMixin):
    __tablename__ = 'TB_REFRESH_TOKEN'

    # Registered Claim
    sub: str = 'Refresh'
    # Redefine fields to define SA's column on metadata
    # JWT token ID
    jti = db.Column(db_module.PrimaryKeyType,
                    db.Sequence('SQ_RefreshToken_UUID'),
                    primary_key=True)
    # Expiration Unix Time
    exp = db.Column(db.DateTime, nullable=False)
    # Audience, User, Token holder
    user = db.Column(db_module.PrimaryKeyType,
                     db.ForeignKey('TB_USER.uuid'),
                     nullable=False)
    # We need to change all refresh tokens' role when user's role is changed
    role = db.Column(db.String, nullable=True)
    otp = db.Column(db.String, nullable=False)
    ip_addr = db.Column(db.String, nullable=False)

    # Backref
    usertable: user_module.User = db.relationship(
                                    'User',
                                    primaryjoin=user == user_module.User.uuid,
                                    backref=db.backref('refresh_tokens',
                                                       order_by='RefreshToken.modified_at.desc()'))

    user_agent = db.Column(db.String, nullable=False)
    # Token data for sending notification on specific client device.
    # Only available on mobile.
    client_token = db.Column(db.String, nullable=True)

    @classmethod
    def from_usertable(cls, userdata: user_module.User) -> 'RefreshToken':
        new_token = cls()
        new_token.usertable = userdata
        new_token.role = userdata.role
        new_token.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
        new_token.exp += refresh_token_valid_duration
        new_token.otp = str(int(secrets.token_hex(8), 16)).zfill(24)
        return new_token

    @classmethod
    def from_token(cls, jwt_input: str, key: str, algorithm: str = 'HS256') -> 'RefreshToken':
        token_data = jwt.decode(jwt_input, key=key, algorithms=algorithm)
        current_time: datetime.datetime = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

        current_api_ver: str = flask.current_app.config.get('RESTAPI_VERSION')
        if token_data.get('api_ver', '') != current_api_ver:
            raise jwt.exceptions.InvalidTokenError('Token api version mismatch')
        if token_data.get('sub', '') != cls.sub:
            raise jwt.exceptions.InvalidTokenError('Token sub mismatch')
        if not token_data.get('otp', ''):
            raise jwt.exceptions.InvalidTokenError('OTP field is empty')

        # Get token data from DB using JTI
        target_token = db.session.query(RefreshToken)\
            .filter(RefreshToken.jti == token_data.get('jti', -1))\
            .filter(RefreshToken.exp > current_time)\
            .first()
        if not target_token:
            raise jwt.exceptions.InvalidTokenError('RefreshToken not found on DB')

        if type(target_token.exp) == int:
            target_token.exp = datetime.datetime.fromtimestamp(target_token.exp, utils.UTC)

        token_exp_time = target_token.exp.replace(tzinfo=utils.UTC)
        if token_exp_time < current_time:
            raise jwt.exceptions.ExpiredSignatureError('Refresh token has reached expiration time')

        db_token_exp = target_token.exp.replace(tzinfo=utils.UTC)
        cookie_token_exp = datetime.datetime.fromtimestamp(token_data.get('exp', 0), utils.UTC)

        if target_token.user == int(token_data.get('user', '')) and db_token_exp == cookie_token_exp:
            return target_token
        else:
            raise jwt.exceptions.InvalidTokenError('RefreshToken information mismatch')

    def create_token(self, key: str, algorithm: str = 'HS256', exp_reset: bool = True) -> str:
        if exp_reset:
            self.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
            self.exp += refresh_token_valid_duration

        if self.jti and self.jti <= -1:
            self.jti = None
            db.session.add(self)

        if not self.otp:
            self.otp = str(int(secrets.token_hex(8), 16)).zfill(24)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return super().create_token(key, algorithm)


class AdminToken(TokenBase):
    # Registered Claim
    sub: str = 'Admin'

    _refresh_token: 'RefreshToken' = None

    @classmethod
    def from_token(cls, jwt_input: str, key: str, algorithm: str = 'HS256') -> 'AccessToken':
        parsed_token = super().from_token(jwt_input, key, algorithm)

        # Check if token's revoked
        redis_key = RedisKeyType.TOKEN_REVOKE.as_redis_key(parsed_token.jti)
        redis_result = redis_db.get(redis_key)
        if redis_result and redis_result == b'revoked':
            raise jwt.exceptions.InvalidTokenError('This token was revoked')

        return parsed_token

    @classmethod
    def from_refresh_token(cls, refresh_token: 'RefreshToken'):
        # Check refresh token exp
        current_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

        if type(refresh_token.exp) == int:
            token_exp_time = datetime.datetime.fromtimestamp(refresh_token.exp, utils.UTC)
        else:
            if refresh_token.exp:
                token_exp_time = refresh_token.exp.replace(tzinfo=utils.UTC)
            else:
                token_exp_time = None
        if (not token_exp_time) or (token_exp_time < current_time):
            raise jwt.exceptions.ExpiredSignatureError('Refresh token has reached expiration time')

        new_token = AdminToken()
        new_token._refresh_token = refresh_token
        new_token.exp = datetime.datetime.utcnow().replace(microsecond=0)  # Drop microseconds
        new_token.exp += admin_token_valid_duration
        new_token.user = refresh_token.user
        # Admin token's JTI must be same with Refresh token's.
        new_token.jti = refresh_token.jti
        new_token.role = refresh_token.role
        new_token.otp = refresh_token.otp

        return new_token


def create_login_data(user_data: user_module.User,
                      user_agent: str, csrf_token: str, client_token: typing.Optional[str],
                      ip_addr: str, key: str, algorithm: str = 'HS256')\
                            -> tuple[list[tuple[str, str]], dict[str, str]]:
    restapi_version = flask.current_app.config.get('RESTAPI_VERSION')
    server_name = flask.current_app.config.get('SERVER_NAME')
    https_enable = flask.current_app.config.get('HTTPS_ENABLE', True)
    cookie_samesite = ('None' if https_enable else 'Lax') if restapi_version == 'dev' else 'strict'

    response_header: list[tuple[str, str]] = list()
    response_data: dict[str, dict[str, str]] = dict()

    refresh_token = RefreshToken.from_usertable(user_data)
    refresh_token.user_agent = user_agent
    refresh_token.client_token = client_token
    refresh_token.ip_addr = ip_addr
    refresh_token_jwt = refresh_token.create_token(key, algorithm, True)
    refresh_token_cookie = utils.cookie_creator(
        name='refresh_token',
        data=refresh_token_jwt,
        domain=server_name if restapi_version != 'dev' else None,
        path=f'/api/{refresh_token.api_ver}/account',
        expires=utils.cookie_datetime(refresh_token.exp),
        samesite=cookie_samesite,
        secure=https_enable)
    response_header.append(('Set-Cookie', refresh_token_cookie))
    response_data['refresh_token'] = {'exp': refresh_token.exp, }

    access_token = AccessToken.from_refresh_token(refresh_token)
    access_token_jwt = access_token.create_token(key+csrf_token, algorithm, True)
    response_data['access_token'] = {
        'exp': refresh_token.exp,
        'token': access_token_jwt,
    }

    if refresh_token.role and 'admin' in refresh_token.role:
        # This user is admin, so we need to issue admin token and send this with cookie.
        admin_token = AdminToken.from_refresh_token(refresh_token)
        admin_token_jwt = admin_token.create_token(key)
        admin_token_cookie = utils.cookie_creator(
            name='admin_token',
            data=admin_token_jwt,
            domain=server_name if restapi_version != 'dev' else None,
            path=f'/api/{refresh_token.api_ver}/admin',
            expires=utils.cookie_datetime(refresh_token.exp),
            samesite=cookie_samesite,
            secure=https_enable)
        response_header.append(('Set-Cookie', admin_token_cookie))
        response_data['admin_token'] = {'exp': admin_token.exp, }

    return response_header, response_data


def refresh_login_data(refresh_token_jwt: str,
                       user_agent: str, csrf_token: str, client_token: typing.Optional[str],
                       ip_addr: str, key: str, algorithm: str = 'HS256')\
                            -> tuple[list[tuple[str, str]], dict[str, str]]:
    restapi_version = flask.current_app.config.get('RESTAPI_VERSION')
    server_name = flask.current_app.config.get('SERVER_NAME')
    https_enable = flask.current_app.config.get('HTTPS_ENABLE', True)
    cookie_samesite = ('None' if https_enable else 'Lax') if restapi_version == 'dev' else 'strict'

    response_header: list[tuple[str, str]] = list()
    response_data: dict[str, dict[str, str]] = dict()

    refresh_token = RefreshToken.from_token(refresh_token_jwt, key)

    # Check device type/OS/browser using User-Agent.
    # We'll refresh token only if it's same with db records
    try:
        db_ua: ua_parser.UserAgent = ua.parse(refresh_token.user_agent)
        req_ua: ua_parser.UserAgent = ua.parse(user_agent)

        check_result: bool = all((
            all((
                db_ua.is_mobile == req_ua.is_mobile,
                db_ua.is_tablet == req_ua.is_tablet,
                db_ua.is_pc == req_ua.is_pc,
            )),
            db_ua.os.family == req_ua.os.family,
            db_ua.browser.family == req_ua.browser.family,
        ))
        if not check_result:
            raise jwt.exceptions.InvalidTokenError('User-Agent does not compatable')
    except jwt.exceptions.InvalidTokenError:
        raise
    except Exception:
        raise jwt.exceptions.InvalidTokenError('User-Agent not parsable')

    # Refresh token will be re-issued only when there's 10 days left until token expires
    token_exp_time = refresh_token.exp.replace(tzinfo=utils.UTC)
    if token_exp_time < datetime.datetime.utcnow().replace(tzinfo=utils.UTC) + datetime.timedelta(days=10):
        try:
            # Re-issue refresh token
            refresh_token.user_agent = user_agent
            refresh_token.ip_addr = ip_addr
            refresh_token_jwt = refresh_token.create_token(key, algorithm, True)
            db.session.commit()

            refresh_token_cookie = utils.cookie_creator(
                name='refresh_token',
                data=refresh_token_jwt,
                domain=server_name if restapi_version != 'dev' else None,
                path=f'/api/{refresh_token.api_ver}/account',
                expires=utils.cookie_datetime(refresh_token.exp),
                samesite=cookie_samesite,
                secure=https_enable)

            response_header.append(('Set-Cookie', refresh_token_cookie))
        except Exception:
            # It's OK to ignore error while re-issueing refresh token
            db.session.rollback()
        finally:
            # We need to send refresh token expiration date anyway
            response_data['refresh_token'] = {'exp': refresh_token.exp, }

    # If client requests token change, then we need to commit this on db
    elif refresh_token.client_token != client_token:
        refresh_token.client_token = client_token
        db.session.commit()

    # Now, re-issue Access token
    # Access token can always be re-issued
    access_token = AccessToken.from_refresh_token(refresh_token)
    access_token_jwt = access_token.create_token(key+csrf_token, algorithm, True)
    response_data['access_token'] = {
        'exp': access_token.exp,
        'token': access_token_jwt,
    }

    # Re-issue Admin token if user is admin
    if refresh_token.role and 'admin' in refresh_token.role:
        admin_token = AdminToken.from_refresh_token(refresh_token)
        admin_token_jwt = admin_token.create_token(key)
        admin_token_cookie = utils.cookie_creator(
            name='admin_token',
            data=admin_token_jwt,
            domain=server_name if restapi_version != 'dev' else None,
            path=f'/api/{refresh_token.api_ver}/admin',
            expires=utils.cookie_datetime(refresh_token.exp),
            samesite=cookie_samesite,
            secure=https_enable)
        response_header.append(('Set-Cookie', admin_token_cookie))
        response_data['admin_token'] = {'exp': admin_token.exp, }

    return response_header, response_data
