class Config:
    MYSQL_HOST = "localhost"
    MYSQL_USER = "root"
    MYSQL_PASSWORD = ""
    MYSQL_DB = "orthoguide"
    
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:@localhost/orthoguide"
    SQLALCHEMY_TRACK_MODIFICATIONS = False