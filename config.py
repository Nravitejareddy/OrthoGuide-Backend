class Config:
    MYSQL_HOST = "127.0.0.1"
    MYSQL_USER = "root"
    MYSQL_PASSWORD = ""
    MYSQL_DB = "orthoguide"
    
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@127.0.0.1/orthoguide"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}