from sanic import Sanic

from api import api_bp

app = Sanic('shop')

app.blueprint(
    api_bp,
)
