import uvicorn
import datetime
from starlette.applications import Starlette
from starlette.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.staticfiles import StaticFiles
from secure import SecureHeaders
from settings import SECRET_KEY, database, templates, DB_URI
from models import UserAuthentication, Ad, Rent
from tortoise.contrib.starlette import register_tortoise
from accounts.routes import accounts_routes
from ads.routes import ads_routes

# Security Headers are HTTP response headers that, when set,
# can enhance the security of your web application
# by enabling browser security policies.
# more on https://secure.readthedocs.io/en/latest/headers.html
secure_headers = SecureHeaders()

app = Starlette(debug=True)
app.mount("/static", StaticFiles(directory="../static"), name="static")
app.mount("/accounts", accounts_routes)
app.mount("/ads", ads_routes)
app.add_middleware(AuthenticationMiddleware, backend=UserAuthentication())
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# middleware for secure headers
@app.middleware("http")
async def set_secure_headers(request, call_next):
    response = await call_next(request)
    secure_headers.starlette(response)
    return response


@app.route("/", methods=["GET"])
async def index(request):
    results = "Home page"
    return templates.TemplateResponse(
        "index.html", {
            "request": request,
            "results": results
        }
    )


@app.route("/filter-search", methods=["GET", "POST"])
async def filter_search(request):
    """
    Filter search questions by city and available ads (not rented ads in
    required time)
    """
    # ads in required time
    try:
        city = request.query_params['city']
        start = request.query_params['start']
        end = request.query_params['end']
        if start > end:
            return RedirectResponse(url='/')
        between = await Rent.filter(
            start_date__lte=datetime.datetime.strptime(
                end, "%Y-%m-%d").date(),
            end_date__gte=datetime.datetime.strptime(
                start, "%Y-%m-%d").date()
        ).values_list()
        rented = list(set([i[-1] for i in between]))
        print(rented)
        if rented:
            results = (
                await Ad.all()
                .prefetch_related("user", "ad_image", "ad", 'ad_rent')
                .filter(city=city,
                        id__not_in=rented
                        )
                .order_by("-id")
            )
        # if ad not in rented list (never rented)
        # return ads by city filter
        else:
            results = (
                await Ad.all()
                .prefetch_related("user", "ad_image", "ad", 'ad_rent')
                .filter(city=city)
                .order_by("-id")
            )
    # if form is empty return all ads
    except KeyError:
        results = (
            await Ad.all()
            .prefetch_related("user", "ad_image", "ad", 'ad_rent')
            .order_by("-id")
        )
    return templates.TemplateResponse(
        "ads/filter_search.html", {
            "request": request,
            "results": results,
            "count": len(results)
        }
    )


@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


@app.exception_handler(404)
async def not_found(request, exc):
    """
    Return an HTTP 404 page.
    """
    template = "404.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context, status_code=404)


@app.exception_handler(500)
async def server_error(request, exc):
    """
    Return an HTTP 500 page.
    """
    template = "500.html"
    context = {"request": request}
    return templates.TemplateResponse(template, context, status_code=500)

register_tortoise(
    app, db_url=DB_URI, modules={"models": ["models"]}, generate_schemas=True
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
