FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       default-libmysqlclient-dev \
       netcat-traditional \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装Python依赖
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目文件
COPY . /app/

# 设置启动脚本权限
RUN chmod +x /app/docker-entrypoint.sh
RUN if [ -f /app/celery-entrypoint.sh ]; then chmod +x /app/celery-entrypoint.sh; fi

# 创建日志目录
RUN mkdir -p /app/logs && chmod -R 777 /app/logs

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["/app/docker-entrypoint.sh"] 