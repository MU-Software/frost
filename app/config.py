import json
import os
import secrets


class Config:
    DEBUG = False
    TESTING = False
    SERVER_IS_ON_PROXY = bool(os.environ.get('SERVER_IS_ON_PROXY', False))
    X_FOR_LEVEL = int(os.environ.get('X_FOR_LEVEL', 0))
    X_PROTO_LEVEL = int(os.environ.get('X_PROTO_LEVEL', 0))
    X_HOST_LEVEL = int(os.environ.get('X_HOST_LEVEL', 0))
    X_PORT_LEVEL = int(os.environ.get('X_PORT_LEVEL', 0))
    X_PREFIX_LEVEL = int(os.environ.get('X_PREFIX_LEVEL', 0))

    JSON_AS_ASCII = False
    PROJECT_NAME = os.environ.get('PROJECT_NAME')
    BACKEND_NAME = os.environ.get('BACKEND_NAME')
    SERVER_NAME = os.environ.get('SERVER_NAME', None)
    # `HTTPS_ENABLE` will be disabled only if $env:HTTPS_ENABLE is 'false'
    HTTPS_ENABLE = os.environ.get('HTTPS_ENABLE', True) != 'false'

    # Referer is not a typo. See HTTP referer header.
    # This will be enabled only if $env:REFERER_CHECK is 'false'
    REFERER_CHECK = os.environ.get('REFERER_CHECK', True) != 'false'
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    DEVELOPMENT_KEY = os.environ.get('DEVELOPMENT_KEY')
    LOCAL_DEV_CLIENT_PORT = None

    RESTAPI_VERSION = os.environ.get('RESTAPI_VERSION')
    # `ACCOUNT_ROUTE_ENABLE` will be disabled only if $env:ACCOUNT_ROUTE_ENABLE is 'false'
    ACCOUNT_ROUTE_ENABLE = os.environ.get('ACCOUNT_ROUTE_ENABLE', True) != 'false'
    DROP_ALL_REFRESH_TOKEN_ON_LOAD = os.environ.get('DROP_ALL_REFRESH_TOKEN_ON_LOAD', True) != 'false'

    FILE_MANAGEMENT_ROUTE_ENABLE = os.environ.get('FILE_MANAGEMENT_ROUTE_ENABLE', False) == 'true'
    FILE_UPLOAD_IMAGE_WEB_FRIENDLY_CHECK = os.environ.get('FILE_UPLOAD_IMAGE_WEB_FRIENDLY_CHECK', False) == 'true'
    try:
        FILE_UPLOAD_ALLOW_EXTENSION = json.loads(os.environ.get('FILE_UPLOAD_ALLOW_EXTENSION', '[]'))
    except Exception:
        print('Failed to load FILE_UPLOAD_ALLOW_EXTENSION.\n'
              'Please check the value is a valid JSON array.')
        FILE_UPLOAD_ALLOW_EXTENSION = []

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DB_URL')

    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
    REDIS_HOST = os.environ.get('REDIS_HOST')
    REDIS_PORT = int(os.environ.get('REDIS_PORT'))
    REDIS_DB = int(os.environ.get('REDIS_DB'))

    # This will enable only if $env:MAIL_ENABLE is 'false'
    MAIL_ENABLE = os.environ.get('MAIL_ENABLE', True) != 'false'
    MAIL_PROVIDER = os.environ.get('MAIL_PROVIDER', 'AMAZON')
    MAIL_DOMAIN = os.environ.get('MAIL_DOMAIN', None)
    SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION = os.environ.get(
        'SIGNIN_POSSIBLE_AFTER_MAIL_VERIFICATION', True) != 'false'

    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', None)
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', None)
    GOOGLE_REFRESH_TOKEN = os.environ.get('GOOGLE_REFRESH_TOKEN', None)


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False

    SQLALCHEMY_ECHO = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DB_URL', 'sqlite:///:memory:')
    # SQLALCHEMY_BINDS = {  # Use this when multiple DB connections are needed
    #     'default': SQLALCHEMY_DATABASE_URI,
    # }

    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')

    LOCAL_DEV_CLIENT_PORT = int(os.environ.get('LOCAL_DEV_CLIENT_PORT'))\
        if os.environ.get('LOCAL_DEV_CLIENT_PORT') else None


class TestingConfig(Config):
    DEBUG = False
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


config_by_name = dict(
    development=DevelopmentConfig,
    testing=TestingConfig,
    production=ProductionConfig,
)
