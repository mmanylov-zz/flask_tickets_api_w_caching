import os
from enum import Enum, unique
basedir = os.path.abspath(os.path.dirname(__file__))


@unique
class TicketStatus(Enum):
    OPEN = 'открыт'
    CLOSED = 'закрыт'
    ANSWERED = 'отвечен'
    WAITING_FOR_ANSWER = 'ожидает ответа'


class Config(object):
    DEBUG = False
    TESTING = False
    CSRF_ENABLED = True
    SECRET_KEY = 'this-really-needs-to-be-changed'
    SQLALCHEMY_DATABASE_URI = 'postgresql://ticketsuser:easypass@localhost/tickets'
    CACHE_TYPE = 'RedisCache'
    # CACHE_REDIS_DB = 2
    CACHE_KEY_PREFIX = 'cache_'
    CACHE_DEFAULT_TIMEOUT = 300


class ProductionConfig(Config):
    DEBUG = False


class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
