import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "super-secret-key")
    DATABASE_URL = os.getenv("DATABASE_URL")
    SUPERADMIN_LINK = os.getenv("SUPERADMIN_LINK")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cloudinary credentials
    CLOUD_NAME = os.getenv("CLOUD_NAME")
    CLOUD_API_KEY = os.getenv("CLOUD_API_KEY")
    CLOUD_API_SECRET = os.getenv("CLOUD_API_SECRET")

    # Optional: fail-fast if Cloudinary vars missing
    if not all([CLOUD_NAME, CLOUD_API_KEY, CLOUD_API_SECRET]):
        raise ValueError("Cloudinary credentials not set. Add CLOUD_NAME, CLOUD_API_KEY, CLOUD_API_SECRET.")
