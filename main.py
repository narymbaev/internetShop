from sanic import Sanic, response
from sanic.response import text

app = Sanic("MyHelloWorldApp")

@app.get("/index")
async def hello_world(request):
    return response.json({'asdf00': 'asdf'})

app.get_app(
    'Myqwe',
     force_create=True)