import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    MYSQL_HOST = "localhost"
    MYSQL_USER = "root"
    MYSQL_PASSWORD = ""
    MYSQL_DB = "orthoguide"

    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@localhost/orthoguide"
    SQLALCHEMY_TRACK_MODIFICATIONS = False