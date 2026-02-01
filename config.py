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