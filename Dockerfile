FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 使用阿里云镜像源并安装系统依赖
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        default-libmysqlclient-dev \
        netcat-traditional \
        pkg-config \
        python3-dev \
        default-mysql-client \
        dos2unix \
        curl \
        dnsutils \
        iputils-ping \
        net-tools \
        iproute2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 先复制requirements.txt以利用Docker缓存
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 创建必要的目录结构，并确保它们存在且有正确权限
RUN mkdir -p /app/logs /app/media /app/staticfiles && \
    chmod -R 777 /app/logs /app/media /app/staticfiles && \
    touch /app/logs/access.log /app/logs/error.log && \
    chmod 666 /app/logs/access.log /app/logs/error.log

# 复制项目文件
COPY . /app/

# 确保目录不被覆盖
RUN mkdir -p /app/logs && chmod -R 777 /app/logs

# 统一转换脚本为unix格式并赋予执行权限
RUN find /app -type f -name "*.sh" -exec dos2unix {} \; && \
    chmod +x /app/*.sh

# 暴露端口
EXPOSE 8000

# 运行应用
ENTRYPOINT ["/app/docker-entrypoint.sh"]