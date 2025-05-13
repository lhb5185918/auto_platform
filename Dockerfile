FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TZ=Asia/Shanghai
ENV LANG=C.UTF-8

# 使用阿里云镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

# 安装系统依赖和dos2unix，防止脚本因换行符问题无法执行
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       default-libmysqlclient-dev \
       netcat-traditional \
       pkg-config \
       python3-dev \
       default-mysql-client \
       dos2unix \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装Python依赖
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 复制项目文件
COPY . /app/

# 统一转换脚本为unix格式并赋予执行权限
RUN find /app -type f -name "*.sh" -exec dos2unix {} \; && \
    chmod +x /app/docker-entrypoint.sh && \
    if [ -f /app/celery-entrypoint.sh ]; then chmod +x /app/celery-entrypoint.sh; fi

# 创建日志目录
RUN mkdir -p /app/logs && chmod -R 777 /app/logs

# 暴露端口
EXPOSE 8000

# 运行应用（用exec方式，防止PID 1信号丢失）
CMD ["/app/docker-entrypoint.sh"]