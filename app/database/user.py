import datetime
import enum
import flask
import jwt
import secrets
import typing
from passlib.hash import argon2

import app.common.utils as utils
import app.database as db_module

db = db_module.db
redis_db = db_module.redis_db
RedisKeyType = db_module.RedisKeyType


class User(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_USER'
    uuid = db.Column(db_module.PrimaryKeyType, db.Sequence('SQ_User_UUID'), primary_key=True)
    id = db.Column(db.String(collation='NOCASE'), unique=True, nullable=False)
    nickname = db.Column(db.String(collation='NOCASE'), unique=True, nullable=False)
    password = db.Column(db.String, unique=False, nullable=False)
    pw_changed_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)

    # No, We won't support multiple account
    email = db.Column(db.String(254, collation='NOCASE'), nullable=False, unique=True)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    email_secret = db.Column(db.String, nullable=True)

    last_login_date = db.Column(db.DateTime, nullable=False)
    login_fail_count = db.Column(db.Integer, default=0, nullable=False)
    login_fail_date = db.Column(db.DateTime, nullable=True)

    locked_at = db.Column(db.DateTime, nullable=True)
    why_locked = db.Column(db.String, nullable=True)

    deactivated_at = db.Column(db.DateTime, nullable=True)
    why_deactivated = db.Column(db.String, nullable=True)
    deactivated_by_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=True)
    deactivated_by = db.relationship('User', primaryjoin='User.deactivated_by_id == User.uuid')

    private = db.Column(db.Boolean, default=False, nullable=False)
    description = db.Column(db.String, nullable=True)
    profile_image = db.Column(db.String, nullable=True)  # This will point to user profile image url

    role = db.Column(db.String, default=None, nullable=True)

    posts: list = None  # placeholder for backref

    @classmethod
    def get_by_uuid(cls, uuid: int):
        raise NotImplementedError('This method must not be called')

    def check_password(self, pw: str) -> bool:
        pw = utils.normalize(pw)

        if not self.password:
            return False

        # Try verification with password they entered without trimming.
        # If it fails, silently try it with trimming.
        try:
            result = argon2.verify(pw, self.password)
            if not result:
                result = argon2.verify(pw.strip(), self.password)
            return result
        except Exception:
            return False

    def change_password(self, orig_pw: str, new_pw: str, force_change: bool = False) -> tuple[bool, str]:
        # Returns False if this fails, and returns True when it success
        # We'll trim space on user input, Google also do this.
        # https://ux.stackexchange.com/q/75686
        new_pw = utils.normalize(new_pw).strip()
        pw_str_check = utils.is_passwordsafe(new_pw)
        if pw_str_check:
            return False, pw_str_check

        if not force_change:
            orig_pw = utils.normalize(orig_pw).strip()

            if not self.check_password(orig_pw):
                return False, 'WRONG_PASSWORD'

        if new_pw.lower() in (self.id.lower(), self.email.lower(), self.nickname.lower()):
            return False, 'PW_REUSED_ON_ID_EMAIL_NICK'

        try:
            self.password = argon2.hash(new_pw)
        except Exception:
            return False, 'UNKNOWN_ERROR'

        try:
            db.session.commit()
            return True, ''
        except Exception:
            db.session.rollback()
            return False, 'DB_ERROR'

    def change_id(self,
                  pw: str,
                  new_id: str,
                  force_change: bool = False,
                  db_commit: bool = True) -> tuple[bool, str]:
        new_id = utils.normalize(new_id.strip())

        if not force_change and not self.check_password(pw.strip()):
            return False, 'WRONG_PASSWORD'

        if not utils.is_urlsafe(new_id):
            return False, 'FORBIDDEN_CHAR'

        self.id = new_id
        try:
            if db_commit:
                db.session.commit()

            return True, ''
        except Exception:
            db.session.rollback()
            return False, 'DB_ERROR'

    @classmethod
    def try_login(cls, user_ident: str, pw: str) -> tuple[typing.Union[bool, 'User'], str]:
        SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION = flask.current_app.config.get(
            'SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION')

        user_ident = utils.normalize(user_ident.strip())
        pw = utils.normalize(pw.strip())
        # We won't support UUID login,
        # because we won't show UUID to users
        # User.uuid if user_ident.isdecimal()\
        login_type = User.id if user_ident.startswith('@')\
                else User.email if '@' in user_ident and utils.is_email(user_ident)\
                else User.id  # noqa
        if login_type != User.uuid:
            login_type = db.func.lower(login_type)

        if user_ident.startswith('@'):
            user_ident = user_ident[1:]

        self = db.session.query(User).filter(login_type == user_ident).first()
        if not self:
            return False, 'ACCOUNT_NOT_FOUND'

        # If login isn't successful, record failed try
        reason = ''
        if self.locked_at:
            reason = f'ACCOUNT_LOCKED::{self.why_locked}'
        elif self.deactivated_at:
            reason = f'ACCOUNT_DEACTIVATED::{self.why_deactivated}'
        elif not self.check_password(pw):
            reason = 'WRONG_PASSWORD'
        elif SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION and not self.email_verified:
            reason = 'EMAIL_NOT_VERIFIED'

        if reason:
            if reason == 'WRONG_PASSWORD':
                self.login_fail_count += 1
                self.login_fail_date = db.func.now()

                if self.login_fail_count >= 5:
                    self.locked_at = db.func.now()
                    self.why_locked = 'TOO_MUCH_LOGIN_FAIL'
                    reason = 'ACCOUNT_LOCKED::TOO_MUCH_LOGIN_FAIL'
                else:
                    reason += f'::{5 - self.login_fail_count}'
            try:
                db.session.commit()
                return False, reason
            except Exception:
                db.session.rollback()
                return False, 'DB_ERROR'

        # If password is correct and account is not locked, process login.
        self.last_login_date = db.func.now()
        self.login_fail_count = 0
        try:
            db.session.commit()
            return self, ''
        except Exception:
            db.session.rollback()
            return self, 'DB_ERROR'

    def to_dict(self):
        return {
            'uuid': self.uuid,
            'id': self.id,
            'nickname': self.nickname,
            'email': self.email,
            'email_verified': self.email_verified,
            'description': self.description,
            'profile_image': self.profile_image,

            'created_at': self.created_at,
            'modified_at': self.modified_at
        }


class EmailAlreadySentOnSpecificHoursException(Exception):
    def __init__(self, message):
        super().__init__(message)


class EmailTokenAction(enum.Enum):
    # Add enum cases on RedisAction enum class, too
    EMAIL_VERIFICATION = enum.auto()
    EMAIL_PASSWORD_RESET = enum.auto()


class EmailToken(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_EMAILTOKEN'
    uuid = db.Column(db_module.PrimaryKeyType, db.Sequence('SQ_EmailToken_UUID'), primary_key=True)

    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: User = db.relationship('User',
                                 primaryjoin=user_id == User.uuid,
                                 backref=db.backref('email_tokens',
                                                    order_by='EmailToken.created_at.desc()'))

    action = db.Column(db.Enum(EmailTokenAction), nullable=False)
    token = db.Column(db.String, unique=True, nullable=False)
    expired_at = db.Column(db.DateTime, nullable=False)

    @classmethod
    def query_using_token(cls, email_token: str) -> typing.Optional['EmailToken']:
        if not email_token or type(email_token) != str:
            raise ValueError('Attribute `email_token` not set or type is not `str`')

        current_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)
        jwt_token: dict = None
        try:
            jwt_token = jwt.decode(email_token, key=flask.current_app.config.get('SECRET_KEY'), algorithms='HS256')
            jwt_token['data']['action'] = EmailTokenAction(jwt_token['data']['action'])

            # Query Email data
            query_result = db.session.query(EmailToken)\
                .filter(EmailToken.token == email_token)\
                .filter(EmailToken.action == jwt_token['data']['action'])\
                .filter(EmailToken.user_id == jwt_token['user'])\
                .first()

            # Check if email token is expired or not.
            if query_result and query_result.expired_at.replace(tzinfo=utils.UTC) < current_time:
                # Email token is expired, raise jwt.exceptions.ExpiredSignatureError.
                raise jwt.exceptions.ExpiredSignatureError

            return query_result

        except jwt.exceptions.ExpiredSignatureError as err:
            # We need to delete this token from DB as this is not a valid token anymore.
            db.session.delete(db.session.query(EmailToken).filter(EmailToken.token == email_token).first())
            db.session.commit()
            raise err
        except Exception as err:
            db.session.rollback()
            raise err

    @classmethod
    def create(cls, target_user: User, action: EmailTokenAction, expiration_delta: datetime.datetime) -> 'EmailToken':
        try:
            # Check if any mail sent to this address with this action on 48 hours using redis.
            # This can block attacker from spamming to the mail address user.
            redis_key = RedisKeyType[action.name].as_redis_key(target_user.uuid)
            redis_result = redis_db.get(redis_key)
            if redis_result:
                raise EmailAlreadySentOnSpecificHoursException(
                    'There was a request to send password reset mail on this email address on 48 hours.')

            current_time = datetime.datetime.utcnow().replace(tzinfo=utils.UTC)

            # Remove old token if exists
            try:
                old_mail_tokens = db.session.query(EmailToken)\
                    .filter(EmailToken.user_id == target_user.uuid)\
                    .filter(EmailToken.action == EmailTokenAction.EMAIL_PASSWORD_RESET)\
                    .all()
            except Exception:
                pass
            if old_mail_tokens:
                for old_mail_token in old_mail_tokens:
                    # Do not db.session.commit here (performance issue)
                    if old_mail_token.expired_at.replace(tzinfo=utils.UTC) < current_time:
                        # It's just a really old token, delete it.
                        db.session.delete(old_mail_token)
                    else:
                        # Wait, why did this not filtered on Redis checking?
                        raise EmailAlreadySentOnSpecificHoursException(
                            'There was a request to send password reset mail on this email address on 48 hours.')

            # Create email jwt token
            email_token_exp = current_time + expiration_delta
            email_token = jwt.encode({
                'api_ver': flask.current_app.config.get('RESTAPI_VERSION'),
                'iss': flask.current_app.config.get('SERVER_NAME'),
                'exp': email_token_exp,
                'sub': 'Email Auth',
                'jti':  secrets.randbits(64),
                'user': target_user.uuid,
                'data': {'action': action.value, },
            }, key=flask.current_app.config.get('SECRET_KEY'), algorithm='HS256')

            new_email_token: EmailToken = cls()
            new_email_token.user = target_user
            new_email_token.action = action
            new_email_token.token = email_token
            new_email_token.expired_at = email_token_exp

            # Save token data on RDB
            db.session.add(new_email_token)

            # Set 48 hours request blocker
            redis_db.set(redis_key, 'true', expiration_delta)

            # Commit email token data
            db.session.commit()

            return new_email_token
        except Exception as err:
            db.session.rollback()
            raise err
