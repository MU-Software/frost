import flask
import flask_sqlalchemy as fsql
import enum
import re
import secrets
import sqlalchemy.dialects.mysql as sqldlc_mysql
import sqlalchemy.dialects.postgresql as sqldlc_psql
import sqlalchemy.dialects.sqlite as sqldlc_sqlite

import app.common.utils as utils

# We'll manage redis here too.
import redis

# ---------- REDIS Setup ----------
redis_db: redis.StrictRedis = None


class RedisKeyType(utils.EnumAutoName):
    # RedisKeyType's enum values are string, because this will be used on Redis key.
    # This is intended and must not be used on DB column type.
    EMAIL_VERIFICATION = enum.auto()
    EMAIL_PASSWORD_RESET = enum.auto()
    TOKEN_REVOKE = enum.auto()

    def as_redis_key(self, value: str):
        return f'{self.value}={str(value)}'


# ---------- RDB Setup ----------
# Create db object when module loads, but do not connect to app context yet.
db: fsql.SQLAlchemy = fsql.SQLAlchemy(session_options={"autoflush": False})

# ---------- RDB Type Handler ----------
PrimaryKeyType = db.BigInteger().with_variant(sqldlc_psql.BIGINT(), 'postgresql')
PrimaryKeyType = db.BigInteger().with_variant(sqldlc_mysql.BIGINT(), 'mysql')
PrimaryKeyType = db.BigInteger().with_variant(sqldlc_sqlite.INTEGER(), 'sqlite')

# ---------- RDB IntegrityError Case Checker ---------
IntegrityCase = [
    'FAILED_NOT_NULL',
    'FAILED_UNIQUE',
    'FAILED_FOREIGN_KEY',
    'FAILED_PRIMARY_KEY',
    'FAILED_CHECK',
]


def IntegrityCaser_sqlite(err_str):
    def default_column_extractor(errstr):
        return errstr.split(':')[1].split(',')[0].split('.')[1].strip()

    case_data = {
        # https://github.com/sqlite/sqlite/blob/master/src/vdbe.c#L1055
        'NOT NULL': (IntegrityCase[0], default_column_extractor),  # FAILED_NOT_NULL  # noqa
        'UNIQUE':   (IntegrityCase[1], default_column_extractor),  # FAILED_UNIQUE  # noqa
        'CHECK':    (IntegrityCase[4], default_column_extractor),  # FAILED_CHECK  # noqa
        'FOREIGN KEY': (IntegrityCase[2], lambda x: []),  # FAILED_FOREIGN_KEY

        # https://github.com/openstack/oslo.db/blob/master/oslo_db/sqlalchemy/exc_filters.py#L177
        'PRIMARY KEY': (IntegrityCase[3], ),  # FAILED_PRIMARY_KEY
    }

    for case_substring, column_analyze in case_data.items():
        if case_substring in err_str:
            return column_analyze[0], column_analyze[1](err_str)

    return (None, None)


def IntegrityCaser_psycopg2(err, pgcode):
    def unique_column_extractor(err):
        return re.findall(
                    r'Key \((\S+)\)=\((\S+)\) already exists.',
                    err.__cause__.diag.message_detail)[0][0]

    def null_column_extractor(err):
        return re.findall(
                    r'null value in column "(\S+)" violates not-null constraint',
                    err.__cause__.diag.message_primary)

    def fk_column_extractor(err):
        return re.findall(
                    r'Key \((\S+)\)=\((\S+)\) is not present in table "(\S+)".',
                    err.__cause__.diag.message_detail)[0][0]

    case_data = {
        '23000': ('', lambda x: []),  # INTEGRITY_CONSTRAINT_VIOLATION @ PSQL
        '23001': ('', lambda x: []),  # RESTRICT_VIOLATION @ PSQL
        '23502': (IntegrityCase[0], null_column_extractor),  # FAILED_NOT_NULL
        '23503': (IntegrityCase[2], fk_column_extractor),  # FAILED_FOREIGN_KEY
        '23505': (IntegrityCase[1], unique_column_extractor),  # FAILED_UNIQUE
        '23514': (IntegrityCase[4], lambda x: []),  # FAILED_CHECK
        '23P01': ('', lambda x: []),  # EXCLUSION_VIOLATION @ PSQL
    }

    column_analyze = case_data.get(pgcode, (None, None))
    if not column_analyze[0]:
        return (None, None)

    return column_analyze[0], column_analyze[1](err)


def IntegrityCaser(err):
    if db.engine.driver == 'psycopg2':
        return IntegrityCaser_psycopg2(err, err.orig.pgcode)

    elif db.engine.driver == 'pysqlite':
        return IntegrityCaser_sqlite(err.__cause__.args[0])

    else:
        print(f'Integrity Caser for {db.engine.driver} '
              'is not implemented yet!')
        raise err


# Default model mixins
class DefaultModelMixin:
    created_at = db.Column(db.DateTime, default=db.func.now())
    modified_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())
    commit_id = db.Column(db.String, default=secrets.token_hex, onupdate=secrets.token_hex)

    @classmethod
    def get_by_uuid(cls, uuid: int, return_query: bool = True):
        if not hasattr(cls, 'uuid'):
            raise NotImplementedError(f'{cls.__name__} does not have uuid attribute')
        if not hasattr(cls, 'query'):
            raise NotImplementedError(f'{cls.__name__} does not look like a SQLAlchemy table')

        target_query = db.session.query(cls).filter(cls.uuid == uuid)
        if return_query:
            return target_query
        return target_query.first()


def init_app(app: flask.Flask):
    # Connect to app context
    db.init_app(app)
    # Dummy query for checking connection to DB
    db.session.execute('select 1')

    global redis_db

    redis_db = redis.StrictRedis(
        password=app.config.get('REDIS_PASSWORD'),
        host=app.config.get('REDIS_HOST'),
        port=app.config.get('REDIS_PORT'),
        db=app.config.get('REDIS_DB'))

    import app.database.user as user  # noqa
    import app.database.board as board  # noqa
    import app.database.jwt as jwt_module  # noqa
    import app.database.uploaded_file as filedb_module  # noqa
    import app.database.project_table as project_table  # noqa

    # Create all tables only IF NOT EXISTS
    # The reason why I didn't use create_all is,
    # checkfirst isn't supported on create_all.
    for table in db.get_tables_for_bind():
        table.create(checkfirst=True, bind=db.engine)

    if app.config.get('RESTAPI_VERSION') == 'dev' and app.config.get('DROP_ALL_REFRESH_TOKEN_ON_LOAD', True):
        # Drop some DB tables when on dev mode
        # db.drop_all()
        db.session.query(jwt_module.RefreshToken).delete()
        db.session.commit()
        # Also, flush all keys in redis DB
        redis_db.flushdb()  # no asynchronous

    # init_app must return app
    return app
