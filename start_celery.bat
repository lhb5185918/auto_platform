@echo off
echo 正在启动Celery服务...

REM 激活虚拟环境（如果需要的话，取消下面这行的注释）
call .venv\Scripts\activate.bat

REM 启动Celery worker (Windows兼容模式)
start cmd /k "echo 启动Celery Worker && celery -A djangoProject4 worker -l info --pool=solo --concurrency=1"

REM 等待2秒
timeout /t 2 /nobreak >nul

REM 启动Celery beat
start cmd /k "echo 启动Celery Beat && celery -A djangoProject4 beat -l info"

echo Celery服务已启动。
echo Worker和Beat服务在单独的命令窗口中运行。
echo 关闭这些窗口以停止服务。 