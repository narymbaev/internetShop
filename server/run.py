import logging

from app import app
from data.psql import Database

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@app.listener('before_server_start')
async def before_server_start(_app, _loop):
    logger.debug('[BEGIN] before_server_start()')

    from settings import Settings

    await Database.instance().connect(
        database=Settings.instance().psql.database,
        host=Settings.instance().psql.host,
        port=Settings.instance().psql.port,
        user=Settings.instance().psql.user,
        password=Settings.instance().psql.password,
    )

    logger.debug('[END] before_server_start()')


@app.listener('after_server_stop')
async def after_server_stop(_app, _loop):
    logger.debug('[BEGIN] after_server_stop()')

    await Database.instance().close()

    logger.debug('[END] after_server_stop()')


if __name__ == '__main__':
    logger.debug('run()')
    try:
        app.run('127.0.0.1', port=8888, access_log=True)
    except Exception as e:
        print(e)
