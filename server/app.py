import os

from sanic import Sanic, response, Request
from sanic_ext import render
from data.psql import Database
from sanic.exceptions import NotFound

app = Sanic('shop')
app.extend(templating_enable_async=True, templating_path_to_templates="templates")


@app.route('/')
@app.ext.template("index.html", name='home')
async def index(request: Request):
    q = request.get_args().get('q')

    items = await Database.instance().fetch(
        '''
        SELECT *
        FROM public.items
        '''
    )
    category = await Database.instance().fetch(
        '''
        SELECT category
        FROM public.items
        '''
    )
    category = {it for it in category}
    context = {"items": items, "category": category}
    return context


@app.exception(NotFound)
async def ignore_404s(request, exception):
    return response.text("Yep, I totally found the page: {}".format(request.url))

