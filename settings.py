from starlette.config import Config
from starlette.templating import Jinja2Templates

# Configuration from environment variables or '.env' file.
config = Config(".env")
DB_URI = config("DB_URI")
SECRET_KEY = config("SECRET_KEY")
templates = Jinja2Templates(directory="templates")
BASE_HOST = "http://localhost:8000"
CLOUDINARY_API_KEY = config("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = config("CLOUDINARY_API_SECRET")
# uncomment for Dropzone upload to filesystem
# UPLOAD_FOLDER = "static/uploads"
