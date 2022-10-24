import logging
from functools import wraps

logger = logging.getLogger(__name__)

def loggable(func):
    name = func.__qualname__

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug(f'{name} -> args: {args}, kwargs {kwargs}')
        return func(*args, **kwargs)

    return wrapper
