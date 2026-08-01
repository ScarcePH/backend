import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ## LOCAL
    # SQLALCHEMY_DATABASE_URI = "postgresql://localhost/test-deploy"
    ##PROD
    SQLALCHEMY_DATABASE_URI = os.environ.get("DB_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 5,
        "max_overflow": 2,
        "pool_timeout": 30,
        "pool_recycle": 300,
        "pool_pre_ping": True,
        "connect_args": {"sslmode": "require"},
    }

    @classmethod
    def validate_required_environment(cls):
        required = (
            "APP_SECRET",
            "VERIFY_TOKEN",
            "PAGE_ACCESS_TOKEN",
            "PAGE_APP_ID",
            "REDIS_URL",
            "DB_URI",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
            "EMAIL_WORKER_URL",
            "JWT_SECRET_KEY",
        )
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(missing)
            )
