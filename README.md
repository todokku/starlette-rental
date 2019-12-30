Example of [Starlette](https://www.starlette.io/) Q&A application made with [Tortoise ORM](https://tortoise-orm.readthedocs.io/en/latest/) and PostgreSQL.

Open terminal and run:

```shell
virtualenv -p python3 envname
cd envname
source bin/activate
git clone https://github.com/sinisaos/starlette-rental.git
cd starlette-rental
pip install -r requirements.txt
sudo -i -u yourpostgresusername psql
CREATE DATABASE rental;
\q
touch .env
## put this two line in .env file
## DB_URI="postgres://username:password@localhost:5432/rental"
## SECRET_KEY="your secret key"
uvicorn app:app --port 8000 --host 0.0.0.0 --proxy-headers
```
You have two options for upload images:
1. DropzoneJS for upload images to filesystem
2. Upload images to [Cloudinary](https://cloudinary.com/) because Heroku filesystem is not suitable for file upload.  
   More info on link https://help.heroku.com/K1PPS2WM/why-are-my-file-uploads-missing-deleted

For Heroku deployment change DB_URI in .env file, BASE_HOST in settings.py, sign up to [Cloudinary](https://cloudinary.com/) free account, set CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET do .env file and everything shoud be fine. 


