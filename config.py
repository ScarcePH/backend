import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ## LOCAL
    # SQLALCHEMY_DATABASE_URI = "postgresql://localhost/scarce-db"
    ##PROD
    SQLALCHEMY_DATABASE_URI = os.environ.get("DB_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
