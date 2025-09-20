import os

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # Flask secret key
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "super-secret-key")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Admin
    SUPERADMIN_LINK = os.getenv("SUPERADMIN_LINK")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()

    # IMGBB API key
    IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
    if not IMGBB_API_KEY:
        raise ValueError(
            "IMGBB_API_KEY is not set! "
            "Add it to Render environment variables."
        )
