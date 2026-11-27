# 使用 Python 精简镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装（如果你的项目没有 requirements.txt，请先执行 pip freeze > requirements.txt）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目源代码（.dockerignore 会排除大文件夹）
COPY . .

# 暴露应用端口（根据实际情况修改，如 5000、8000 等）
EXPOSE 8000

# 启动命令（将 main.py 替换为你自己的入口文件名，例如 app.py、run.py 等）
CMD ["python", "api_server.py"]