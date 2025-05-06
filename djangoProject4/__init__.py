import pymysql

pymysql.install_as_MySQLdb()

# 导入celery应用
from .celery import app as celery_app

__all__ = ('celery_app',)
