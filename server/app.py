from sanic import Sanic, response, Request, json, request
from werkzeug.security import generate_password_hash, check_password_hash
from sanic.response import text, redirect, SanicException
from sanic.views import HTTPMethodView
from data.psql import Database
from sanic.exceptions import NotFound
import jwt
from datetime import datetime, timedelta
from functools import wraps
from sanic_ext import render
from sanic_jwt import Initialize

app = Sanic('shop')
app.config['SECRET_KEY'] = 'fd3f59ea06e041498613d81e5b9438f5'
app.extend(templating_enable_async=True, templating_path_to_templates="templates")


class Error(SanicException):
    message = 'Error occured'


def token_required(f):
    @wraps(f)
    async def decorater(*args, **kwargs):
        token = await Database.instance().fetchval(
            '''
            SELECT token
            FROM public.auth_token
            '''
        )
        if token:
            token = token.strip()
        if not token:
            return redirect(app.url_for('login'))
            # return json({'message': 'there is no token'})
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms='HS256')
            print(data)
            # kwargs['user'] = user
        except:
            await Database.instance().execute(
                '''
                DELETE FROM public.auth_token
                '''
            )
            return redirect(app.url_for('login'))
            # return json({'message': 'token is invalid'})
        return await f(*args, **kwargs)
    return decorater


@app.route('login/', name='login', methods=['GET', 'POST'])
async def login(request):
    # token = jwt.encode({'user': username, 'exp': datetime.utcnow() + timedelta(seconds=10)}, app.config['SECRET_KEY'])
    message = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            context = {'message': 'Invalid input'}
            return await render('registration/login.html', context=context)
        user = await Database.instance().fetchrow(
            '''
            SELECT *
            FROM public.user
            WHERE name = $1
            ''', username
        )
        if user:
            hashed_password = user.get('password').strip()
            checker = check_password_hash(hashed_password, password)
            if checker:
                token = jwt.encode({'user_id': user['id'], 'exp': datetime.utcnow() + timedelta(seconds=7)}, app.config['SECRET_KEY'])
                await Database.instance().execute(
                    '''
                    INSERT INTO public.auth_token
                    (token)
                    VALUES ($1) 
                    ''', token
                )
                url = app.url_for('items')
                return redirect(url)
            message = 'login or password is NOT CORRECT'
        else:
            message = 'login or password is not correct'
    context = {'message': message}
    return await render('registration/login.html', context=context,)


class Items(HTTPMethodView):
    @app.ext.template("index.html")
    @token_required
    async def get(self, request: Request):
        q = request.args.get('q')
        if q:
            category_id = await Database.instance().fetchval(
                '''
                SELECT id
                FROM public.category
                WHERE name ILIKE $1
                ''', q
            )

            items = await Database.instance().fetch(
                '''
                SELECT *
                FROM public.goods
                WHERE category_id = $1
                ''', category_id
            )

        else:
            items = await Database.instance().fetch(
                '''
                SELECT *
                FROM public.goods
                '''
            )

        category = await Database.instance().fetch(
            '''
            SELECT name
            FROM public.category
            '''
        )
        context = {'items': items, "category": category, 'item_name': q.title() if q else ""}
        return context


class Item(HTTPMethodView):
    @app.ext.template('detail.html')
    async def get(self, request: Request, pk):
        item = await Database.instance().fetchrow(
            '''
            SELECT *
            FROM public.goods
            WHERE id = $1
            ''', int(pk)
        )
        pre_quantity = await Database.instance().fetchrow(
            '''
            SELECT quantity
            FROM public.cart_item
            WHERE product_id = $1
            ''', int(pk)
        )
        pre_quantity = pre_quantity.get('quantity') if pre_quantity else 0
        return {'item': item, 'quantity_in_cart': pre_quantity}

    async def post(self, request, pk):
        quantity = int(request.form.get('quantity'))
        something = await Database.instance().fetchrow(
            '''
            SELECT *
            FROM public.cart_item
            WHERE product_id = $1
            ''', int(pk)
        )
        if something:  # if there is a item in the cart, it will change the quantity
            await Database.instance().execute(
                '''
                UPDATE public.cart_item
                SET quantity = $1
                WHERE product_id = $2
                ''', quantity, int(pk)
            )
        else:  # if there is no item in cart
            if quantity > 0:
                await Database.instance().execute(
                    '''
                    INSERT INTO public.cart_item
                    (quantity, cart_id, product_id)
                    VALUES ($1, $2, $3)
                    ''', quantity, 1, int(pk)
                )
        url = app.url_for('item', pk=pk)
        return redirect(url)

    async def put(self, request: Request):
        return text('update the item')

    async def delete(self, request: Request, pk):
        if request.method == "DELETE":
            await Database.instance().execute(
                '''
                DELETE
                FROM public.cart_item
                WHERE product_id = $1
                ''', int(pk)
            )
        return text('delete the item')


class Shopcart(HTTPMethodView):

    @app.ext.template('cart_page.html')
    async def get(self, request: Request):
        cart_items = await Database.instance().fetch(
            '''
            SELECT product_id
            FROM public.cart_item
            WHERE cart_id = 1
            '''
        )
        ids = [str(item_id.get('product_id')) for item_id in cart_items]
        condition = 'id = ' + ' OR id = '.join(ids)
        items = await Database.instance().fetch(
            '''
            SELECT *
            FROM public.goods
            WHERE {condition}
            '''.format(condition=condition)
        )
        context = {'items': items}
        return context


app.add_route(Items.as_view(), 'items/', name='items')
app.add_route(Item.as_view(), 'items/<pk>/', name='item')
app.add_route(Shopcart.as_view(), 'shopcart/', name='shopcart')


@app.route('/admin/create', methods=['GET', 'POST'], name='create-item')
@app.ext.template('admin/create.html')
async def admin(request):
    if request.method == 'GET':
        brands = await Database.instance().fetch(
            '''
            SELECT *
            FROM public.brands
            '''
        )
        category = await Database.instance().fetch(
            '''
            SELECT *
            FROM public.category
            '''
        )
        context = {'brands': brands, 'category': category}

        return context

    if request.method == 'POST':
        item_tile = request.form.get('item_title')
        description = request.form.get('description')
        brand = request.form.get('brand')
        category = request.form.get('category')
        cost = request.form.get('cost')
        quantity = request.form.get('quantity')

        await Database.instance().execute(
            '''
            INSERT INTO public.goods (title, description, brand_id, category_id, cost, quantity)
            VALUES ($1, $2, $3, $4, $5, $6)
            ''', item_tile, description, 1, 1, int(cost), int(quantity)
        )
        url = app.url_for('list-item')
        return redirect(url)


@app.route('admin/list', methods=['GET', 'POST'], name='list-item')
@app.ext.template('admin/list.html')
async def list_item(request):
    if request.method == 'GET':
        items = await Database.instance().fetch(
            '''
            SELECT *
            FROM public.goods
            ORDER BY id
            '''
        )
    context = {'items': items}
    return context


@app.route('admin/<pk>/edit', name='edit-item')
@app.ext.template('admin/edit.html')
async def edit(request, pk):
    context = {}
    return context


@app.route('admin/<pk>/delete', name='delete-item')
@app.ext.template('admin/delete.html')
async def delete(request, pk):
    await Database.instance().execute(
        '''
        DELETE
        FROM public.goods
        WHERE id = $1
        ''', int(pk)
    )
    url = app.url_for('list-item')
    return redirect(url)


@app.exception(NotFound)
async def ignore_404s(request, exception):
    return response.text("Yep, I totally found the page: {}".format(request.url))
