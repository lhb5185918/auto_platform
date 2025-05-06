import os
from celery import Celery
from django.conf import settings
import platform

# 设置默认Django设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoProject4.settings')

app = Celery('djangoProject4')

# 使用字符串表示，这样worker不用序列化配置对象
app.config_from_object('django.conf:settings', namespace='CELERY')

# 针对Windows平台的特殊配置
if platform.system() == 'Windows':
    app.conf.broker_connection_retry_on_startup = True
    app.conf.worker_pool_restarts = True
    app.conf.task_acks_late = True
    # 使用solo池
    app.conf.worker_pool = 'solo'

# 自动发现任务
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# 显式添加任务模块
app.conf.imports = ('test_platform.tasks',)

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}') 