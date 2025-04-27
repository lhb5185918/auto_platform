from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = '设置数据库时区为北京时间'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # 设置全局时区
            cursor.execute("SET GLOBAL time_zone = '+08:00'")
            # 设置会话时区
            cursor.execute("SET time_zone = '+08:00'")
            # 刷新权限
            cursor.execute("FLUSH PRIVILEGES")
            
        self.stdout.write(self.style.SUCCESS('成功设置数据库时区为北京时间'))