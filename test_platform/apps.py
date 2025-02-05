from django.apps import AppConfig
from django.db import connection


class TestPlatformConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'test_platform'

    def ready(self):
        # 在应用启动时设置数据库时区
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+08:00'")
            cursor.execute("SET sql_mode = 'STRICT_TRANS_TABLES'")
