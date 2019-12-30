# import os
import cloudinary.uploader
import cloudinary
import datetime
import math
# import random
import aiofiles
from settings import (
    templates,
    BASE_HOST,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
    # , UPLOAD_FOLDER
)
from starlette.responses import RedirectResponse
from starlette.authentication import requires
from tortoise.query_utils import Q
from tortoise.transactions import in_transaction
from ads.forms import (
    AdForm,
    AdEditForm,
    ReviewForm,
    ReviewEditForm,
    RentForm
)
from models import (
    Ad,
    User,
    Image,
    Review,
    Rent,
    Notification,
    ADMIN
)


async def ads_all(request):
    """
    All ads
    """
    path = request.url.path
    page_query = request.query_params['page']
    result = await Ad.all()
    count = len(result)
    page = int(page_query)
    per = 8
    totalPages = int(math.ceil(count / per))
    offset = per * (page - 1)
    results = await Ad.all().prefetch_related(
        "user", "ad_image", "ad").limit(per).offset(offset).order_by('-id')
    return templates.TemplateResponse(
        "ads/ads.html",
        {
            "request": request,
            "results": results,
            "path": path,
            "totalPages": totalPages,
            "page_query": page_query,
        },
    )


async def ad(request):
    """
    Single ad
    """
    id = request.path_params["id"]
    path = request.url.path
    results = await Ad.get(id=id).prefetch_related("user", "ad_rent")
    # update ad views per session
    session_key = 'viewed_ad_{}'.format(results.id)
    if not request.session.get(session_key, False):
        results.view += 1
        await results.save()
        request.session[session_key] = True
    image_results = await Image.all().filter(ad_image_id=id)
    review_results = (await Review.all()
                      .prefetch_related("review_user", "ad")
                      .filter(ad__id=id)
                      .order_by("-id")
                      )
    # if no reviews
    try:
        review_avg = sum(r.review_grade for r in review_results) / \
            len(review_results)
    except ZeroDivisionError:
        review_avg = None

    # proccesing form for booking ad
    data = await request.form()
    form = RentForm(data)
    if request.method == "POST" and form.validate():
        session_user = request.user.username
        result = await User.get(username=session_user)
        start = form.start_date.data
        end = form.end_date.data
        try:
            between = await Rent.filter(
                start_date__lte=end,
                end_date__gte=start,
                ad_rent_id=id
            )

            now = datetime.datetime.now().date()
            diff = (now - start).total_seconds()
            if diff > 0:
                rent_error = "Both dates can't be in the past."

            days = (end - start).days
            if days < 1:
                rent_error = "The minimum rental period is one day."

            if any(between):
                rent_error = "Already rented in that time."
            return templates.TemplateResponse(
                    "ads/ad.html",
                    {
                        "request": request,
                        "item": results,
                        "path": path,
                        "images": image_results,
                        "review_results": review_results,
                        "review_count": len(review_results),
                        "review_avg": review_avg,
                        "form": form,
                        "rent_error": rent_error
                    },
                )
        except:
            query = Rent(
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                client_id=result.id,
                ad_rent_id=results.id,
            )
            await query.save()
            # notification to ad owner
            notification_query = Notification(
                message=f"{results.title} booked by {session_user}",
                created=datetime.datetime.now(),
                is_read=0,
                sender_id=result.id,
                recipient_id=results.user.id
            )
            await notification_query.save()
            return RedirectResponse(BASE_HOST + path, status_code=302)
    return templates.TemplateResponse(
        "ads/ad.html",
        {
            "request": request,
            "item": results,
            "path": path,
            "images": image_results,
            "review_results": review_results,
            "review_count": len(review_results),
            "review_avg": review_avg,
            "form": form
        },
    )


@requires("authenticated")
async def ad_create(request):
    """
    Ad create form
    """
    session_user = request.user.username
    results = await User.get(username=session_user)
    data = await request.form()
    form = AdForm(data)
    title = form.title.data
    if request.method == "POST" and form.validate():
        query = Ad(
            title=title,
            slug="-".join(title.lower().split()),
            content=form.content.data, created=datetime.datetime.now(),
            view=0,
            price=form.price.data,
            city=form.city.data,
            address=form.address.data,
            user_id=results.id
        )
        await query.save()
        return RedirectResponse(url="/ads/images", status_code=302)
    return templates.TemplateResponse(
        "ads/ad_create.html", {"request": request, "form": form}
    )


@requires("authenticated")
async def ad_images(request):
    return templates.TemplateResponse(
        "ads/images.html", {
            "request": request,
            "BASE": BASE_HOST
        }
    )


async def write_file(path, body):
    async with aiofiles.open(path, 'wb') as f:
        await f.write(body)
    f.close()


@requires("authenticated")
async def upload(request):
    """
    upload images to Cloudinary because Heroku filesystem is not suitable \
    for files upload. More info on link
    https://help.heroku.com/K1PPS2WM/why-are-my-file-uploads-missing-deleted
    """
    result = await Ad.all()
    # last inserted ad id
    aid = result[-1].id
    data = await request.form()
    iter_images = data.multi_items()
    num_of_images = len([i for i in iter_images if i[1] != ''])
    # list of images paths
    images = [data["images" + str(i)] for i in range(num_of_images)]
    # save images path and last inserted ad id to db
    for item in images:
        async with in_transaction() as conn:
            await conn.execute_query(
                f"INSERT INTO image (path, ad_image_id) \
                    VALUES ('{item}', {aid});"
            )
    return RedirectResponse(url="/ads/?page=1", status_code=302)

"""
- uncomment for Dropzone upload to filesystem

@requires("authenticated")
async def upload(request):
    result = await Ad.all()
    # last inserted ad id
    aid = result[-1].id
    data = await request.form()
    # convert multidict to list of items for multifile upload
    iter_images = data.multi_items()
    # read item and convert to bytes
    byte_images = [await item[1].read() for item in iter_images]
    list_of_paths = []
    # write bytes to file in filesystem
    # name of file with random
    for upload_file in byte_images:
        file_path = f"{UPLOAD_FOLDER}/{random.randint(100,100000)}.jpeg"
        list_of_paths.append(file_path)
        await write_file(file_path, upload_file)
    # store file paths to db and link to single ad
    for item in list_of_paths:
        async with in_transaction() as conn:
            await conn.execute_query(
                f"INSERT INTO image (path, ad_image_id) \
                    VALUES (\"{item}\", {aid});"
            )
    return RedirectResponse(url="/ads/?page=1", status_code=302)
"""


@requires("authenticated")
async def ad_edit(request):
    """
    Ad edit form
    """
    id = request.path_params["id"]
    session_user = request.user.username
    results = await User.get(username=session_user)
    ad = await Ad.get(id=id)
    images = await Image.all().filter(ad_image_id=ad.id)
    data = await request.form()
    form = AdEditForm(data)
    new_form_value, form.content.data = form.content.data, ad.content
    title = form.title.data
    if request.method == "POST" and form.validate():
        query = Ad(
            id=ad.id,
            title=title,
            slug="-".join(title.lower().split()),
            content=new_form_value,
            created=datetime.datetime.now(),
            view=ad.view,
            price=form.price.data,
            city=form.city.data,
            address=form.address.data,
            user_id=results.id,
        )
        await query.save()
        return RedirectResponse(url=f"/ads/image-edit/{ad.id}",
                                status_code=302
                                )
    return templates.TemplateResponse(
        "ads/ad_edit.html", {
            "request": request,
            "form": form,
            "ad": ad,
            "images": images,
        }
    )


@requires("authenticated")
async def image_edit(request):
    aid = request.path_params["id"]
    # count remaining images
    img_count = await Image.all().filter(ad_image_id=aid).count()
    return templates.TemplateResponse(
        "ads/image_edit.html", {
            "request": request,
            "BASE": BASE_HOST,
            "aid": aid,
            "img_count": img_count
        }
    )


@requires("authenticated")
async def edit_upload(request):
    # edited ad id
    aid = int((request.url.path).split('/')[-1])
    img_count = await Image.all().filter(ad_image_id=aid).count()
    data = await request.form()
    # list of remaining images paths
    images = [data["images" + str(i)] for i in range(3-img_count)]
    # save images path and last inserted ad id to db
    for item in images:
        async with in_transaction() as conn:
            await conn.execute_query(
                f"INSERT INTO image (path, ad_image_id) \
                    VALUES ('{item}', {aid});"
            )
    return RedirectResponse(BASE_HOST + f"/ads/edit/{aid}",
                            status_code=302
                            )


"""
- uncomment for Dropzone upload to filesystem

@requires("authenticated")
async def edit_upload(request):
    if request.method == "POST":
        # edited ad id
        aid = int((request.url.path).split('/')[-1])
        data = await request.form()
        # convert multidict to list of items for multifile upload
        iter_images = data.multi_items()
        # read item and convert to bytes
        byte_images = [await item[1].read() for item in iter_images]
        list_of_paths = []
        # write bytes to file in filesystem
        # name of file with random
        for upload_file in byte_images:
            file_path = f"{UPLOAD_FOLDER}/{random.randint(100,100000)}.jpeg"
            list_of_paths.append(file_path)
            await write_file(file_path, upload_file)
        # store file paths to db and link to single ad
        for item in list_of_paths:
            print(item)
            async with in_transaction() as conn:
                await conn.execute_query(
                    f"INSERT INTO image (path, ad_image_id) \
                        VALUES ('{item}', {aid});"
                )
        return RedirectResponse(BASE_HOST + f"/ads/edit/{aid}#loaded",
                                status_code=302
                                )
"""


@requires("authenticated")
async def image_delete(request):
    """
    Delete image on edit
    """
    id = request.path_params["id"]
    form = await request.form()
    aid = form["aid"]
    if request.method == "POST":
        # delete related image from filesystem
        # uncomment for Dropzone upload to filesystem
        # img = await Image.get(id=id)
        # os.remove(img.path)
        img = await Image.get(id=id)
        public_id = (img.path).split('/')[-1].split('.')[0]
        cloudinary.config(
            cloud_name="rkl",
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
        cloudinary.uploader.destroy(public_id)
        await Image.get(id=id).delete()
        return RedirectResponse(url=f"/ads/edit/{aid}", status_code=302)


@requires("authenticated")
async def ad_delete(request):
    """
    Delete ad
    """
    id = request.path_params["id"]
    if request.method == "POST":
        # delete images from filesystem
        images = await Image.all().filter(ad_image_id=id)
        # for img in images:
        # os.remove(img.path)
        cloudinary.config(
            cloud_name="rkl",
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
        public_ids = [
            (img.path).split('/')[-1].split('.')[0] for img in images
            ]
        cloudinary.api.delete_resources(public_ids)
        await Ad.get(id=id).delete()
        if request.user.username == ADMIN:
            return RedirectResponse(url="/accounts/dashboard", status_code=302)
        return RedirectResponse(url="/accounts/profile", status_code=302)


@requires("authenticated")
async def review_create(request):
    """
    Review form
    """
    id = int(request.query_params['next'].split('/')[2])
    next = request.query_params['next']
    results = await Ad.get(id=id).prefetch_related("user")
    session_user = request.user.username
    data = await request.form()
    form = ReviewForm(data)
    result = await User.get(username=session_user)
    if request.method == "POST" and form.validate():
        query = Review(
            content=form.content.data,
            created=datetime.datetime.now(),
            review_grade=form.grade.data,
            ad_id=results.id,
            review_user_id=result.id,
        )
        await query.save()
        return RedirectResponse(BASE_HOST + next, status_code=302)
    return templates.TemplateResponse(
        "ads/review_create.html", {
            "request": request,
            "form": form,
            "next": next
        }
    )


@requires("authenticated")
async def review_edit(request):
    """
    Review edit form
    """
    id = request.path_params["id"]
    review = await Review.get(id=id)
    data = await request.form()
    form = ReviewEditForm(data)
    new_form_value, form.content.data = form.content.data, review.content
    if request.method == "POST" and form.validate():
        query = Review(
            id=review.id,
            content=new_form_value,
            created=datetime.datetime.now(),
            review_grade=form.grade.data,
            ad_id=review.ad_id,
            review_user_id=review.review_user_id,
        )
        await query.save()
        if request.user.username == ADMIN:
            return RedirectResponse(url="/accounts/dashboard", status_code=302)
        return RedirectResponse(url="/accounts/profile", status_code=302)
    return templates.TemplateResponse(
        "ads/review_edit.html", {
            "request": request,
            "form": form,
            "review": review
        }
    )


@requires("authenticated")
async def review_delete(request):
    """
    Delete review
    """
    id = request.path_params["id"]
    if request.method == "POST":
        await Review.get(id=id).delete()
        if request.user.username == ADMIN:
            return RedirectResponse(url="/accounts/dashboard", status_code=302)
        return RedirectResponse(url="/accounts/profile", status_code=302)


async def search(request):
    """
    Search questions
    """
    try:
        q = request.query_params['q']
        results = (
            await Ad.all()
            .prefetch_related("user", "ad_image", "ad")
            .filter(Q(title__icontains=q) |
                    Q(content__icontains=q) |
                    Q(city__icontains=q) |
                    Q(address__icontains=q) |
                    Q(price__icontains=q) |
                    Q(user__username__icontains=q)).distinct()
            .order_by("-id")
        )
    except KeyError:
        results = (
            await Ad.all()
            .prefetch_related("user", "ad_image", "ad_rent", "ad")
            .order_by("-id")
        )
    return templates.TemplateResponse(
        "ads/search.html", {
            "request": request,
            "results": results,
            "count": len(results)
        }
    )


async def maps(request):
    """
    Map view
    """
    city = request.path_params["city"]
    results = await Ad.all()
    return templates.TemplateResponse(
        "ads/map.html", {
            "request": request,
            "results": results,
            "city": city
        }
    )
