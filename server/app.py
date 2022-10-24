from sanic import Sanic, response, Request, json as js
from sanic.cookies import Cookie, CookieJar
from werkzeug.security import generate_password_hash, check_password_hash
from sanic.response import text, redirect, SanicException
from sanic.views import HTTPMethodView
from data.psql import Database
from sanic.exceptions import NotFound
import jwt
from datetime import datetime, timedelta
from functools import wraps
from sanic_ext import render
from sanic_jwt import Initialize, exceptions
from sanic_session import Session, InMemorySessionInterface
from auth.handlers import check_password, signJWT, decodeJWT

import re

app = Sanic('shop')
app.config['SECRET_KEY'] = 'fd3f59ea06e041498613d81e5b9438f5'
app.extend(templating_enable_async=True, templating_path_to_templates="templates")
session = Session(app, interface=InMemorySessionInterface(cookie_name='session_id'))


def format_number(number: str):
    number = number.replace("(", "")
    number = number.replace(")", "")
    number = number.replace(" ", "")
    if number[0] == '8':
        number = '+7' + number[1:]
    return number


def format_email(email: str):
    email = email.strip()
    email = email.replace(" ", "")
    return email


def check_email(email: str):
    pattern = "^[a-zA-Z0-9-_]+@[a-zA-Z0-9]+\.[a-z]{1,3}$"
    if re.match(pattern, email):
        return True
    return False


def check_phone_number(number: str):
    pattern = "^(\+?77|87)(\d{9})$"
    number = format_number(number)
    if re.match(pattern, number):
        return True
    return False


# Return True if there is a same message from same messenger
async def has_message(message, messenger_id, user_id):
    data = await Database.instance().fetchrow(
        '''
        SELECT *
        FROM public.message
        WHERE body = $1 AND messenger_id = $2 AND user_id = $3
        ''', message, messenger_id, user_id
    )
    if data:
        return True
    return False


async def has_number(number, label_id, user_id):
    data = await Database.instance().fetchrow(
        '''
        SELECT *
        FROM public.phone_number
        WHERE number = $1 AND label_id = $2 AND user_id = $3
        ''', number, label_id, user_id
    )
    if data:
        return True
    return False


async def has_email(email, user_id):
    data = await Database.instance().fetchrow(
        '''
        SELECT *
        FROM public.email
        WHERE value = $1 AND user_id = $2
        ''', email, user_id
    )
    if data:
        return True
    return False


async def add_message(message, messenger_id, user_id):
    await Database.instance().execute(
        '''
        INSERT INTO public.message (body, messenger_id, user_id)
        VALUES ($1, $2, $3)
        ''', message, messenger_id, user_id
    )


async def add_number(number, label_id, user_id):
    await Database.instance().execute(
        '''
        INSERT INTO public.phone_number (number, label_id, user_id)
        VALUES ($1, $2, $3)
        ''', number, label_id, user_id
    )


async def add_email(email, user_id):
    await Database.instance().execute(
        '''
        INSERT INTO public.email (value, user_id)
        VALUES ($1, $2)
        ''', email, user_id
    )


async def get_messenger_id(messenger: str):
    messenger_id = await Database.instance().fetchval(
        '''
        SELECT id
        FROM public.messenger
        WHERE name = $1
        ''', messenger
    )
    return messenger_id


async def get_label_id(label: str):
    label_id = await Database.instance().fetchval(
        '''
        SELECT id
        FROM public.label
        WHERE name = $1
        ''', label
    )
    return label_id


async def add_to_database(messages, phone_numbers, emails, user_id):
    for message, messengers in messages.items():
        for messenger in messengers:
            messenger_id = await get_messenger_id(messenger)
            if not await has_message(message, messenger_id, user_id):
                await add_message(message, messenger_id, user_id)

    for number, label in phone_numbers.items():
        label_id = await get_label_id(label)
        if not await has_number(number, label_id, user_id):
            await add_number(number, label_id, user_id)

    for email in emails:
        if not await has_email(email, user_id):
            await add_email(email, user_id)


async def get_messenger(messenger_id):
    messenger = await Database.instance().fetchval(
        '''
        SELECT name
        FROM public.messenger
        WHERE id = $1
        ''', messenger_id
    )
    return messenger


async def get_label(label_id):
    label = await Database.instance().fetchval(
        '''
        SELECT name
        FROM public.label
        WHERE id = $1
        ''', label_id
    )
    return label


async def get_messages(data, user_id):
    lst = []
    data_base = await Database.instance().fetch(
        '''
        SELECT *
        FROM public.message
        WHERE user_id = $1
        ''', user_id
    )
    for i in data_base:
        dct = {}
        dct['message'] = i['body']
        messenger = await get_messenger(i['messenger_id'])
        dct['message_type'] = messenger
        lst.append(dct)
    data['messengers'] = lst


async def get_phone_numbers(data, user_id):
    lst = []
    data_base = await Database.instance().fetch(
        '''
        SELECT *
        FROM public.phone_number
        WHERE user_id = $1
        ''', user_id
    )
    for i in data_base:
        dct = {}
        dct['phone_number'] = i['number']
        label = await get_label(i['label_id'])
        dct['phone_type'] = label
        lst.append(dct)
    data['phone_numbers'] = lst


async def get_emails(data, user_id):
    lst = []
    data_base = await Database.instance().fetch(
        '''
        SELECT *
        FROM public.email
        WHERE user_id = $1
        ''', user_id
    )
    for i in data_base:
        dct = {}
        dct['email'] = i['value']
        lst.append(dct)
    data['emails'] = lst


@app.route('/test', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
async def index(request: Request):
    user_id = 1

    # POST REQUEST
    if request.method == 'POST':
        data = request.json

        phone_numbers = data.get('phone_numbers')
        formatted_numbers = {}

        messages = data.get('messengers')
        formatted_messages = {}

        emails = data.get('emails')
        formatted_emails = []

        # Checking Phone Number
        for data in phone_numbers:
            if data['phone_number'] == "" or data['phone_type'] == "":
                return js({"message": "Please enter phone number and phone type"})
            if check_phone_number(data['phone_number']):
                formatted_numbers[format_number(data['phone_number'])] = data['phone_type']
            else:
                return js({"message": "Please enter phone number in correct format"})

        # Checking Messenger
        for data in messages:
            if data['message'] == "" or data['message_type'] == "":
                return js({"message": "Please enter message and message_type"})
            if formatted_messages.get(data['message']):
                formatted_messages[data['message']].append(data['message_type'])
            else:
                formatted_messages[data['message']] = []
                formatted_messages[data['message']].append(data['message_type'])

        # Checking Email
        for data in emails:
            if data['email'] == "":
                return js({"message": "Please enter email"})
            if check_email(data['email']) and data['email'] not in formatted_emails:
                formatted_emails.append(data['email'])
            else:
                return js({"message": "Please enter valid format of email"})

        await add_to_database(formatted_messages, formatted_numbers, formatted_emails, user_id)

        return js({"message": "successfully added to database"})

    # GET REQUEST
    if request.method == 'GET':
        data = {}
        await get_messages(data, user_id)
        await get_phone_numbers(data, user_id)
        await get_emails(data, user_id)

        return js(data)


# def token_required(f):
#     @wraps(f)
#     async def wrapper(self, request, *args, **kwargs):
#         print("USER id: ", request.ctx.session.get('user_id'))
#         print("Token id: ", request.ctx.session.get('token_id'))
#         user_id = request.ctx.session.get('user_id')
#         if not user_id:
#             return redirect(app.url_for('login'))
#         token = await Database.instance().fetchval(
#             '''
#             SELECT token
#             FROM public.auth_token
#             WHERE user_id = $1
#             ''', user_id
#         )
#         if token:
#             token = token.strip()
#         else:
#             return redirect(app.url_for('login'))
#         try:
#             payload = decodeJWT(token)
#             print('THis is payload: ', payload)
#             request.ctx.session['token_id'] = payload
#             # kwargs['user_id'] = user
#         except:
#             await Database.instance().execute(
#                 '''
#                 DELETE FROM public.auth_token
#                 WHERE user_id = $1
#                 ''', user_id
#             )
#             request.ctx.session['token_id'] = None
#             return redirect(app.url_for('login'))
#             # return json({'message': 'token is invalid'})
#         return await f(self, request, *args, **kwargs)
#     return wrapper
#
#
#
# @app.route('login/', name='login', methods=['GET', 'POST'])
# async def login(request):
#     # token = jwt.encode({'user': username, 'exp': datetime.utcnow() + timedelta(seconds=10)}, app.config['SECRET_KEY'])
#     user_id = request.ctx.session.get('user_id')
#     token_id = request.ctx.session.get('token_id')
#     if user_id and token_id:
#         return redirect(app.url_for('items'))
#     else:
#         message = None
#         if request.method == 'POST':
#             username = request.form.get('username')
#             password = request.form.get('password')
#             if not username or not password:
#                 context = {'message': 'Invalid input'}
#                 return await render('registration/login.html', context=context)
#             user = await Database.instance().fetchrow(
#                 '''
#                 SELECT *
#                 FROM public.user
#                 WHERE name = $1
#                 ''', username
#             )
#             if user:
#                 checker = check_password(user['password'].strip(), password)
#                 if checker:
#                     token = signJWT(user['id'])
#                     await Database.instance().execute(
#                         '''
#                         INSERT INTO public.auth_token
#                         (user_id, token)
#                         VALUES ($1, $2)
#                         ''', user['id'], token
#                     )
#                     request.ctx.session['user_id'] = user['id']
#                     url = app.url_for('items')
#                     return redirect(url)
#                 message = 'login or password is NOT CORRECT'
#             else:
#                 message = 'login or password is not correct'
#         context = {'message': message}
#         return await render('registration/login.html', context=context,)
#
#
# class Items(HTTPMethodView):
#     @app.ext.template("index.html")
#     @token_required
#     async def get(self, request: Request):
#         q = request.args.get('q')
#         if q:
#             category_id = await Database.instance().fetchval(
#                 '''
#                 SELECT id
#                 FROM public.category
#                 WHERE name ILIKE $1
#                 ''', q
#             )
#
#             items = await Database.instance().fetch(
#                 '''
#                 SELECT *
#                 FROM public.goods
#                 WHERE category_id = $1
#                 ''', category_id
#             )
#
#         else:
#             items = await Database.instance().fetch(
#                 '''
#                 SELECT *
#                 FROM public.goods
#                 '''
#             )
#
#         category = await Database.instance().fetch(
#             '''
#             SELECT name
#             FROM public.category
#             '''
#         )
#         context = {'items': items, "category": category, 'item_name': q.title() if q else ""}
#         return context
#
#
# class Item(HTTPMethodView):
#     @app.ext.template('detail.html')
#     async def get(self, request: Request, pk):
#         item = await Database.instance().fetchrow(
#             '''
#             SELECT *
#             FROM public.goods
#             WHERE id = $1
#             ''', int(pk)
#         )
#         pre_quantity = await Database.instance().fetchrow(
#             '''
#             SELECT quantity
#             FROM public.cart_item
#             WHERE product_id = $1
#             ''', int(pk)
#         )
#         pre_quantity = pre_quantity.get('quantity') if pre_quantity else 0
#         return {'item': item, 'quantity_in_cart': pre_quantity}
#
#     async def post(self, request, pk):
#         quantity = int(request.form.get('quantity'))
#         something = await Database.instance().fetchrow(
#             '''
#             SELECT *
#             FROM public.cart_item
#             WHERE product_id = $1
#             ''', int(pk)
#         )
#         if something:  # if there is a item in the cart, it will change the quantity
#             await Database.instance().execute(
#                 '''
#                 UPDATE public.cart_item
#                 SET quantity = $1
#                 WHERE product_id = $2
#                 ''', quantity, int(pk)
#             )
#         else:  # if there is no item in cart
#             if quantity > 0:
#                 await Database.instance().execute(
#                     '''
#                     INSERT INTO public.cart_item
#                     (quantity, cart_id, product_id)
#                     VALUES ($1, $2, $3)
#                     ''', quantity, 1, int(pk)
#                 )
#         url = app.url_for('item', pk=pk)
#         return redirect(url)
#
#     async def put(self, request: Request):
#         return text('update the item')
#
#     async def delete(self, request: Request, pk):
#         if request.method == "DELETE":
#             await Database.instance().execute(
#                 '''
#                 DELETE
#                 FROM public.cart_item
#                 WHERE product_id = $1
#                 ''', int(pk)
#             )
#         return text('delete the item')
#
#
# class Shopcart(HTTPMethodView):
#
#     @app.ext.template('cart_page.html')
#     async def get(self, request: Request):
#         cart_items = await Database.instance().fetch(
#             '''
#             SELECT product_id
#             FROM public.cart_item
#             WHERE cart_id = 1
#             '''
#         )
#         ids = [str(item_id.get('product_id')) for item_id in cart_items]
#         condition = 'id = ' + ' OR id = '.join(ids)
#         items = await Database.instance().fetch(
#             '''
#             SELECT *
#             FROM public.goods
#             WHERE {condition}
#             '''.format(condition=condition)
#         )
#         context = {'items': items}
#         return context
#
#
# app.add_route(Items.as_view(), 'items/', name='items')
# app.add_route(Item.as_view(), 'items/<pk>/', name='item')
# app.add_route(Shopcart.as_view(), 'shopcart/', name='shopcart')
#
#
# @app.route('/admin/create', methods=['GET', 'POST'], name='create-item')
# @app.ext.template('admin/create.html')
# async def admin(request):
#     if request.method == 'GET':
#         brands = await Database.instance().fetch(
#             '''
#             SELECT *
#             FROM public.brands
#             '''
#         )
#         category = await Database.instance().fetch(
#             '''
#             SELECT *
#             FROM public.category
#             '''
#         )
#         context = {'brands': brands, 'category': category}
#
#         return context
#
#     if request.method == 'POST':
#         item_tile = request.form.get('item_title')
#         description = request.form.get('description')
#         brand = request.form.get('brand')
#         category = request.form.get('category')
#         cost = request.form.get('cost')
#         quantity = request.form.get('quantity')
#
#         await Database.instance().execute(
#             '''
#             INSERT INTO public.goods (title, description, brand_id, category_id, cost, quantity)
#             VALUES ($1, $2, $3, $4, $5, $6)
#             ''', item_tile, description, 1, 1, int(cost), int(quantity)
#         )
#         url = app.url_for('list-item')
#         return redirect(url)
#
#
# @app.route('admin/list', methods=['GET', 'POST'], name='list-item')
# @app.ext.template('admin/list.html')
# async def list_item(request):
#     if request.method == 'GET':
#         items = await Database.instance().fetch(
#             '''
#             SELECT *
#             FROM public.goods
#             ORDER BY id
#             '''
#         )
#     context = {'items': items}
#     return context
#
#
# @app.route('admin/<pk>/edit', name='edit-item')
# @app.ext.template('admin/edit.html')
# async def edit(request, pk):
#     context = {}
#     return context
#
#
# @app.route('admin/<pk>/delete', name='delete-item')
# @app.ext.template('admin/delete.html')
# async def delete(request, pk):
#     await Database.instance().execute(
#         '''
#         DELETE
#         FROM public.goods
#         WHERE id = $1
#         ''', int(pk)
#     )
#     url = app.url_for('list-item')
#     return redirect(url)


@app.exception(NotFound)
async def ignore_404s(request, exception):
    return response.text("Yep, I totally found the page: {}".format(request.url))
