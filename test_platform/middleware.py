from django.db import connection
from django.utils import timezone


class TimezoneMiddleware:
    """
    设置数据库会话时区的中间件
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 在每个请求之前设置数据库时区
        with connection.cursor() as cursor:
            cursor.execute("SET time_zone = '+08:00'")
        
        # 处理请求
        response = self.get_response(request)
        
        return response 