import bcrypt
import jwt
from tortoise.models import Model
from tortoise import fields
from starlette.authentication import (
    AuthenticationBackend,
    AuthenticationError,
    SimpleUser,
    AuthCredentials,
)
from settings import SECRET_KEY

# change this line to set another user as admin user
ADMIN = "admin"


class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255)
    email = fields.CharField(max_length=255)
    joined = fields.DatetimeField(auto_now_add=True)
    last_login = fields.DatetimeField(auto_now=True)
    login_count = fields.IntField()
    password = fields.CharField(max_length=255)

    def __str__(self):
        return self.username


class Ad(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    slug = fields.CharField(max_length=255)
    content = fields.TextField()
    created = fields.DatetimeField(auto_now_add=True)
    view = fields.IntField(default=0)
    price = fields.IntField()
    address = fields.CharField(max_length=255)
    city = fields.CharField(max_length=255)
    user = fields.ForeignKeyField(
        'models.User', related_name='user', on_delete=fields.CASCADE)

    def __str__(self):
        return self.title


class Review(Model):
    id = fields.IntField(pk=True)
    content = fields.TextField()
    created = fields.DatetimeField(auto_now_add=True)
    review_grade = fields.IntField()
    review_user = fields.ForeignKeyField(
        'models.User', related_name='review_user', on_delete=fields.CASCADE)
    ad = fields.ForeignKeyField(
        'models.Ad', related_name='ad', on_delete=fields.CASCADE)


class Image(Model):
    id = fields.IntField(pk=True)
    path = fields.CharField(max_length=255)
    ad_image = fields.ForeignKeyField(
        'models.Ad', related_name='ad_image', on_delete=fields.CASCADE)


class Rent(Model):
    id = fields.IntField(pk=True)
    start_date = fields.DateField()
    end_date = fields.DateField()
    client = fields.ForeignKeyField(
        'models.User', related_name='client', on_delete=fields.CASCADE)
    ad_rent = fields.ForeignKeyField(
        'models.Ad', related_name='ad_rent', on_delete=fields.CASCADE)


class Notification(Model):
    id = fields.IntField(pk=True)
    message = fields.CharField(max_length=150)
    created = fields.DatetimeField(auto_now_add=True)
    is_read = fields.BooleanField(default=False)
    sender = fields.ForeignKeyField(
        'models.User', related_name='sender', on_delete=fields.CASCADE)
    recipient = fields.ForeignKeyField(
        'models.User', related_name='recipient', on_delete=fields.CASCADE)


class UserAuthentication(AuthenticationBackend):
    async def authenticate(self, request):
        jwt_cookie = request.cookies.get("jwt")
        if jwt_cookie:
            try:
                payload = jwt.decode(
                    jwt_cookie.encode("utf8"),
                    str(SECRET_KEY),
                    algorithms=["HS256"]
                )
                if SimpleUser(payload["user_id"]).username == ADMIN:
                    return (
                        AuthCredentials(["authenticated", ADMIN]),
                        SimpleUser(payload["user_id"]),
                    )
                else:
                    return (
                        AuthCredentials(["authenticated"]),
                        SimpleUser(payload["user_id"]),
                    )
            except AuthenticationError:
                raise AuthenticationError("Invalid auth credentials")
        else:
            # unauthenticated
            return


def hash_password(password: str):
    return bcrypt.hashpw(password, bcrypt.gensalt())


def check_password(password: str, hashed_password):
    return bcrypt.checkpw(password, hashed_password)


def generate_jwt(user_id):
    payload = {"user_id": user_id}
    token = jwt.encode(payload, str(SECRET_KEY),
                       algorithm="HS256").decode("utf-8")
    return token
