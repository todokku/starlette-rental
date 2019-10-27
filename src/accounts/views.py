import os
import datetime
from settings import templates, BASE_HOST
from starlette.responses import RedirectResponse
from starlette.authentication import requires
from tortoise.transactions import in_transaction
from accounts.forms import RegistrationForm, LoginForm
from models import (
    User,
    Ad,
    Review,
    Notification,
    check_password,
    generate_jwt,
    hash_password,
    ADMIN,
)


async def register(request):
    """
    Validate form, register and authenticate user with JWT token
    """
    results = await User.all()
    data = await request.form()
    form = RegistrationForm(data)
    username = form.username.data
    email = form.email.data
    password = form.password.data
    if request.method == "POST" and form.validate():
        for result in results:
            if email == result.email or username == result.username:
                user_error = "User with that email or username already exists."
                return templates.TemplateResponse(
                    "accounts/register.html",
                    {
                        "request": request,
                        "form": form,
                        "user_error": user_error
                    },
                )
        query = User(
            username=username,
            email=email,
            joined=datetime.datetime.now(),
            last_login=datetime.datetime.now(),
            login_count=1,
            password=hash_password(password),
        )
        await query.save()
        user_query = await User.get(
            username=username)
        hashed_password = user_query.password
        valid_password = check_password(password, hashed_password)
        response = RedirectResponse(url="/", status_code=302)
        if valid_password:
            response.set_cookie(
                "jwt", generate_jwt(user_query.username), httponly=True
            )
            response.set_cookie(
                "admin", ADMIN, httponly=True
            )
        return response
    return templates.TemplateResponse(
        "accounts/register.html", {
            "request": request,
            "form": form
        }
    )


async def login(request):
    """
    Validate form, login and authenticate user with JWT token
    """
    path = request.query_params['next']
    data = await request.form()
    form = LoginForm(data)
    username = form.username.data
    password = form.password.data
    if request.method == "POST" and form.validate():
        try:
            results = await User.get(
                username=username)
            hashed_password = results.password
            valid_password = check_password(password, hashed_password)
            if not valid_password:
                user_error = "Invalid username or password"
                return templates.TemplateResponse(
                    "accounts/login.html",
                    {
                        "request": request,
                        "form": form,
                        "user_error": user_error
                    },
                )
            # update login counter and login time
            results.login_count += 1
            results.last_login = datetime.datetime.now()
            await results.save()
            response = RedirectResponse(BASE_HOST + path, status_code=302)
            response.set_cookie(
                "jwt", generate_jwt(results.username), httponly=True
            )
            response.set_cookie(
                "admin", ADMIN, httponly=True
            )
            return response
        except:  # noqa
            user_error = "Please register you don't have account"
            return templates.TemplateResponse(
                "accounts/login.html",
                {
                    "request": request,
                    "form": form,
                    "user_error": user_error,
                },
            )
    return templates.TemplateResponse("accounts/login.html", {
        "request": request,
        "form": form,
        "path": path
    })


@requires("authenticated")
async def user_delete(request):
    """
    Delete user
    """
    id = request.path_params["id"]
    if request.method == "POST":
        # delete related user images in filesystem
        async with in_transaction() as conn:
            result = await conn.execute_query(
                f"SELECT path FROM image \
                JOIN ad on ad.id = image.ad_image_id \
                JOIN user on user.id = ad.user_id WHERE user.id = {id}"
            )
        image_list = []
        for i in result:
            for k, v in i.items():
                image_list.append(v)
        for img in image_list:
            os.remove(img)
        await User.get(id=id).delete()
        request.session.clear()
        response = RedirectResponse(url="/", status_code=302)
        response.delete_cookie("jwt")
        return response


@requires(["authenticated", ADMIN], redirect="index")
async def dashboard(request):
    if request.user.is_authenticated:
        auth_user = request.user.display_name
        results = await User.all().order_by('-id')
        ads = await Ad.all().order_by('-id')
        reviews = await Review.all().order_by('-id')
        return templates.TemplateResponse(
            "accounts/dashboard.html",
            {
                "request": request,
                "results": results,
                "ads": ads,
                "reviews": reviews,
                "auth_user": auth_user,
            },
        )


@requires("authenticated", redirect="index")
async def profile(request):
    if request.user.is_authenticated:
        auth_user = request.user.display_name
        results = await User.get(username=auth_user)
        ads = await Ad.all().filter(user_id=results.id).order_by('-id')
        reviews = await Review.all().filter(
            review_user_id=results.id).order_by('-id')
        notifications = await Notification.all().prefetch_related(
            'sender').filter(recipient_id=results.id).order_by('-id')
        # unread notifications by profile user
        unread_notifications = await Notification.filter(
            is_read=False,
            recipient=results.id
        )
        # rented ad by session user and from session user
        # i don't know how to make it with orm it's easier with raw sql
        async with in_transaction() as conn:
            rented_by_me = await conn.execute_query(
                f"SELECT ad.title, rent.start_date, rent.end_date, \
                (SELECT username from user WHERE ad.user_id = user.id) as usr FROM ad \
                JOIN rent ON ad.id=rent.ad_rent_id \
                JOIN user ON user.id=ad.user_id WHERE rent.client_id={results.id}"
            )
        async with in_transaction() as conn:
            rented_from_me = await conn.execute_query(
                f"SELECT ad.title, rent.start_date, rent.end_date, \
                (SELECT username from user WHERE rent.client_id = user.id) as usr FROM ad \
                JOIN rent ON ad.id = rent.ad_rent_id \
                JOIN user ON user.id = ad.user_id WHERE user.id={results.id}"
            )
        return templates.TemplateResponse(
            "accounts/profile.html",
            {
                "request": request,
                "results": results,
                "ads": ads,
                "rented_by_me": rented_by_me,
                "rented_from_me": rented_from_me,
                "reviews": reviews,
                "notifications": notifications,
                'unread_notifications': len(unread_notifications),
                "auth_user": auth_user
            }
        )


@requires("authenticated", redirect="index")
async def read_notification(request):
    id = request.path_params["id"]
    if request.method == "POST":
        results = await Notification.get(id=id)
        results.is_read = 1
        await results.save()
        return RedirectResponse(url="/accounts/profile", status_code=302)


async def logout(request):
    request.session.clear()
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("jwt")
    return response
