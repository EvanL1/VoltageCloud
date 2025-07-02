# IoT 设备模拟器 Docker 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir AWSIoTPythonSDK

# 复制应用文件
COPY iot_device_simulator.py .

# 复制证书目录
COPY certificates/ certificates/

# 设置权限
RUN chmod +x iot_device_simulator.py

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 默认命令：运行5分钟，每5秒发送一次数据
CMD ["python", "iot_device_simulator.py", "300", "5"]