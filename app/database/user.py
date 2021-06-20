import typing
from passlib.hash import argon2

import app.common.utils as utils
import app.database as db_module
db = db_module.db


class User(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_USER'
    uuid = db.Column(db_module.PrimaryKeyType, db.Sequence('SQ_User_UUID'), primary_key=True)
    id = db.Column(db.String, unique=True, nullable=False)
    nickname = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, unique=False, nullable=False)
    pw_changed_at = db.Column(db.DateTime, default=db.func.now(), nullable=False)

    # No, We won't support multiple account
    email = db.Column(db.String(254), nullable=False, unique=True)
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

    def change_password(self, orig_pw: str, new_pw: str) -> tuple[bool, str]:
        # Returns False if this fails, and returns True when it success
        # We'll trim space on user input, Google also do this.
        # https://ux.stackexchange.com/q/75686
        orig_pw = utils.normalize(orig_pw)
        new_pw = utils.normalize(new_pw)

        pw_str_check = utils.is_passwordsafe(new_pw)
        if pw_str_check:
            return False, pw_str_check

        if not self.check_password(orig_pw):
            return False, 'WRONG_PASSWORD'

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

    def change_id(self, pw: str, new_id: str) -> tuple[bool, str]:
        new_id = utils.normalize(new_id)

        if self.check_password(pw):
            return False, 'WRONG_PASSWORD'

        if not utils.char_urlsafe(new_id):
            return False, 'FORBIDDEN_CHAR'

        self.id = new_id
        try:
            db.session.commit()
            return True, ''
        except Exception:
            db.session.rollback()
            return False, 'DB_ERROR'

    @classmethod
    def try_login(cls, user_ident: str, pw: str) -> tuple[typing.Union[bool, 'User'], str]:
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

        self = User.query.filter(login_type == user_ident).first()
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
            'description': self.description,
            'profile_image': self.profile_image,

            'created_at': self.created_at,
            'modified_at': self.modified_at
        }


class EmailToken(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_EMAILTOKEN'
    uuid = db.Column(db_module.PrimaryKeyType, db.Sequence('SQ_EmailToken_UUID'), primary_key=True)

    user_id = db.Column(db_module.PrimaryKeyType, db.ForeignKey('TB_USER.uuid'), nullable=False)
    user: User = db.relationship('User',
                                 primaryjoin=user_id == User.uuid,
                                 backref=db.backref('email_tokens',
                                                    order_by='EmailToken.created_at.desc()'))

    action = db.Column(db.String, nullable=False)
    token = db.Column(db.String, unique=True, nullable=False)
    expired_at = db.Column(db.DateTime, nullable=False)
