# 智能教育系统 - 宝塔面板部署文档

> 部署方式：云服务器裸机直跑 + 宝塔面板（BT Panel）可视化管理
> 部署目录约定：`/www/wwwroot/all_tame_channel/`

---

## 一、部署架构概览

```
[用户浏览器]
   │ HTTPS
   ▼
[Nginx 反向代理]  ← 宝塔一键配置 SSL
   │ http://127.0.0.1:8000
   ▼
[FastAPI 服务 (api_server.py)]  ← 宝塔 Python 项目管理器守护
   │
   ├─→ MySQL 8.0 (code_db)        ← 宝塔数据库组件
   ├─→ Redis 7                     ← 宝塔 Redis 组件
   ├─→ ChromaDB (本地 memory/)     ← 持久化向量库
   └─→ 外部服务：阿里云 OSS / DeepSeek / 讯飞 ASR
```

**端口规划：**
- 对外：80 / 443（Nginx）
- 内部：8000（FastAPI，仅 127.0.0.1）
- 内部：3306（MySQL）、6379（Redis）

---

## 二、服务器前置准备

### 2.1 安装宝塔面板
登录云服务器（SSH），执行：
```bash
# Ubuntu/Debian
wget -O install.sh https://download.bt.cn/install/install-ubuntu_6.0.sh && sudo bash install.sh ed8484bec

# CentOS
yum install -y wget && wget -O install.sh https://download.bt.cn/install/install_6.0.sh && sh install.sh ed8484bec
```
装完保存好面板地址、账号、密码。

### 2.2 软件商店安装组件
进入宝塔面板 → **软件商店**，依次安装：
| 组件 | 版本 | 用途 |
|---|---|---|
| Nginx | 1.24+ | 反向代理 |
| MySQL | 8.0（或 5.7） | 主数据库 |
| Redis | 7.x | LLM 缓存 |
| **Python 项目管理器** | 最新 | 守护 FastAPI 进程 |
| Linux 工具集 | - | 含 ffmpeg 等系统包 |

### 2.3 系统依赖（ffmpeg / whisper 必需）
宝塔 → 终端执行：
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y build-essential libssl-dev libffi-dev \
    ffmpeg pkg-config libsndfile1 libgl1-mesa-glx libglib2.0-0

# CentOS
sudo yum install -y gcc gcc-c++ openssl-devel ffi-devel \
    ffmpeg pkgconfig libsndfile mesa-libGL glib2
```

---

## 三、本地：打包代码与数据

### 3.1 打包代码（Windows PowerShell）
在 `e:\PY\all_tame_channel\` 下执行：
```powershell
tar -cvf deploy.tar `
  --exclude='.venv' --exclude='__pycache__' --exclude='.idea' --exclude='.vscode' `
  --exclude='.git' --exclude='.cache_models' --exclude='.proxyai' --exclude='.uploads' `
  --exclude='avatar-sdk-web_demo' --exclude='server-master' `
  --exclude='*.png' --exclude='_test*.py' --exclude='_check_attempts.py' `
  --exclude='compare_*.py' --exclude='train_*.py' --exclude='test_*.py' `
  --exclude='generate_*.py' --exclude='_test.db' --exclude='.dockerignore' --exclude='Dockerfile' `
  api_server.py manager_server.py pyproject.toml uv.lock requirements.txt .gitignore `
  Agent services utils templates prompts docs `
  data models memory rag_knowledge `
  note_data recommendation_data user_features user_voices wrong_answer_data `
  community_data teacher_data user_assessments user_twin predict video_ww `
  output generated_documents key
```

### 3.2 导出 MySQL 数据
```bash
mysqldump -u root -p --databases code_db > code_db.sql
```

### 3.3 单独准备 .env（含密钥，**不入 tar 包**）
保留本地 `.env` 副本，单独上传到服务器。

### 3.4 导出依赖（可选，备用方案）
若不使用 uv 而用 pip 装依赖，本地执行：
```bash
uv export --no-dev --format requirements-txt --output requirements-linux.txt
```
然后手动删除以下行（如有）：
- `pywin32`、`winshell`、`WMI`、`pywin32-ctypes`
- 任何 `@ file:///C:/...` 的本地 wheel 行
- `some-package==0.1`

---

## 四、服务器：上传与解压

### 4.1 上传文件
宝塔 → **文件** → 进入 `/www/wwwroot/`：
1. 新建目录 `all_tame_channel`
2. 上传 `deploy.tar` 到该目录
3. 右键 `deploy.tar` → **解压** → 解压到当前目录
4. 单独上传 `.env` 到 `/www/wwwroot/all_tame_channel/.env`
5. 上传 `code_db.sql` 到 `/root/`（或任意临时位置）

### 4.2 设置目录权限
宝塔终端执行：
```bash
cd /www/wwwroot/all_tame_channel
chown -R www:www .
chmod -R 755 .
# 运行时写入目录放宽
chmod -R 775 memory note_data recommendation_data user_voices \
            wrong_answer_data community_data/uploads output generated_documents \
            Agent/children_agent/static 2>/dev/null
mkdir -p community_data/uploads
```

---

## 五、MySQL 数据导入

### 5.1 创建数据库
宝塔 → **数据库 → 添加数据库**：
- 数据库名：`code_db`
- 用户名：`code_user`（或直接用 root）
- 密码：自定义强密码（记下来，等下填到 .env）
- 访问权限：本地服务器
- 字符集：utf8mb4

### 5.2 导入数据
宝塔终端：
```bash
mysql -u root -p code_db < /www/wwwroot/all_tame_channel/code_db.sql
# 或在宝塔数据库管理界面 → 导入 SQL 文件
```
导入完成后可删除 `code_db.sql`。

---

## 六、Redis 配置

宝塔 → Redis → **修改配置文件**：
1. 设置密码：`requirepass <你的强密码>`
2. 最大内存：`maxmemory 512mb`
3. `maxmemory-policy allkeys-lru`
4. 重启 Redis

---

## 七、配置 .env（关键）

编辑 `/www/wwwroot/all_tame_channel/.env`，改成服务器实际值。**完整变量清单**（扫描代码得到）：

```ini
# ==================== 数据库 ====================
DATABASE_URL=mysql+pymysql://root:<MySQL密码>@127.0.0.1:3306/code_db?charset=utf8mb4

# 人脸识别模块单独配置（如不用可留空但保留）
DB_HOST=127.0.0.1
DB_USER=root
DB_PASSWORD=<MySQL密码>
DB_NAME=student_learning
DB_PORT=3306

# ==================== Redis ====================
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=4
REDIS_PASSWORD=<Redis密码>

# ==================== LLM ====================
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-<你的DeepSeek密钥>
LLM_BASE_URL=https://api.deepseek.com
# 可选：DASHSCOPE_API_KEY=<通义千问密钥>  # PPT生成/朗读Agent需要

# ==================== 阿里云 OSS ====================
OSS_ACCESS_KEY_ID=<你的OSS AK>
OSS_ACCESS_KEY_SECRET=<你的OSS SK>
OSS_ENDPOINT=https://oss-cn-beijing.aliyuncs.com
OSS_BUCKET=all-tame-max-oss

# ==================== 讯飞 ASR ====================
XFYUN_APP_ID=<讯飞 AppID>
XFYUN_API_KEY=<讯飞 API Key>
XFYUN_API_SECRET=<讯飞 API Secret>

# ==================== CORS（生产环境必填）====================
ALLOWED_ORIGINS=https://你的域名.com,https://www.你的域名.com

# ==================== 可选：其他ASR（不使用就留空）====================
# AZURE_SPEECH_KEY=
# AZURE_SPEECH_REGION=
# BAIDU_APP_ID=
# BAIDU_API_KEY=
# BAIDU_SECRET_KEY=
# MOONSHOT_API_KEY=
# QWEN_API_KEY=
# DEEPSEEK_API_KEY=
```

**安全提醒：**
- `.env` 已在 `.gitignore` 中，不要提交到 git
- 宝塔文件管理器设置 `.env` 权限为 `600`（仅所有者可读写）
- 不要把 `.env` 截图发到任何外部群

---

## 八、安装 Python 依赖

### 方案 A：使用 uv（推荐）
宝塔终端：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.bashrc
cd /www/wwwroot/all_tame_channel
uv sync --extra all
```

### 方案 B：使用 pip + requirements-linux.txt
```bash
cd /www/wwwroot/all_tame_channel
python3.12 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements-linux.txt
```

### 方案 C：宝塔 Python 项目管理器自动安装
在第九步创建项目时，让项目管理器读取 `requirements.txt` 自动装。

---

## 九、创建 Python 项目（守护进程）

宝塔 → **Python 项目管理器 → 添加项目**：

| 配置项 | 值 |
|---|---|
| 项目名称 | all_tame_channel |
| 路径 | `/www/wwwroot/all_tame_channel` |
| Python 版本 | 3.12 |
| 项目类型 | FastAPI / 通用 |
| 框架 | FastAPI |
| 启动方式 | 模块启动 |
| 启动命令 | `uvicorn api_server:app --host 127.0.0.1 --port 8000 --workers 1` |
| 安装依赖 | 勾选，指定 `pyproject.toml` 或 `requirements-linux.txt` |
| 启动用户 | www |

**环境变量**：项目设置 → 环境变量 → 把 `.env` 的内容逐行粘进去（或在「配置文件」处保留 `.env` 文件路径，代码已调用 `load_dotenv()` 自动读取）。

启动后看日志，应输出：
```
✅ .env 配置文件已加载
🚀 默认线程池已扩容至 32 线程
✅ 管理端权重配置路由已挂载: /admin/*
✅ 教师端路由已挂载: /teacher/*
✅ 静态文件服务已启动: ...
```

---

## 十、Nginx 反向代理 + SSL

### 10.1 添加站点
宝塔 → **网站 → 添加站点**：
- 域名：`api.你的域名.com`
- 根目录：`/www/wwwroot/all_tame_channel`
- PHP 版本：纯静态
- 数据库：不创建

### 10.2 配置反向代理
站点设置 → **反向代理 → 添加反向代理**：
- 代理名称：`fastapi`
- 目标 URL：`http://127.0.0.1:8000`
- 发送域名：`$host`
- 启用

### 10.3 配置 SSL
站点设置 → **SSL → Let's Encrypt** → 申请 → 勾选**强制 HTTPS**。

### 10.4 Nginx WebSocket 支持（视频通话/智能球必加）
站点设置 → 配置文件，在 `location /` 块内追加：
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_read_timeout 86400s;   # 长连接/SSE 流式输出必需
proxy_buffering off;         # SSE 流式必需
```

---

## 十一、安全放行端口

宝塔 → **安全**：
- 放行：80、443（对外）
- **不放行**：8000、3306、6379（仅本机）
- 云服务器安全组同步放行 80/443

---

## 十二、验证部署

### 12.1 健康检查
宝塔终端：
```bash
curl http://127.0.0.1:8000/docs | head -20    # Swagger 文档
curl https://你的域名.com/docs                  # 经 Nginx
```

### 12.2 接口冒烟测试
```bash
# 通用对话
curl -X POST https://你的域名.com/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"deploy_test","user_input":"你好"}'

# 学习计划
curl -X GET "https://你的域名.com/study_plan?user_id=deploy_test"

# 管理端路由
curl https://你的域名.com/admin/weights
```

### 12.3 日志排查
- 应用日志：宝塔 Python 项目管理器 → 项目 → 日志
- Nginx 日志：`/www/wwwlogs/你的域名.com.log`
- MySQL 慢日志：宝塔 MySQL → 慢日志
- Redis 日志：宝塔 Redis → 日志

---

## 十三、文件导出清单（最终版）

| 类型 | 文件 | 处理 |
|---|---|---|
| 代码包 | `deploy.tar` | 上传到 `/www/wwwroot/all_tame_channel/` 解压 |
| 配置 | `.env` | 单独上传，权限 600 |
| 数据库 | `code_db.sql` | 导入后删除 |
| 依赖清单（可选） | `requirements-linux.txt` | 用 pip 时需要 |

**不传的文件：**
- `avatar-sdk-web_demo/`（252MB，仅 demo）
- `server-master/`、`_test*.py`、`train_*.py`、`generate_*.py`、`compare_*.py`、`test_*.py`
- `*.png` 对比图、`_test.db`、`Dockerfile`、`.dockerignore`
- `.venv/`、`__pycache__/`、`.idea/`、`.vscode/`、`.git/`

---

## 十四、常见问题

**Q1：启动报 `ModuleNotFoundError: No module named 'xxx'`**
A：依赖没装全。`uv sync --extra all` 或 `pip install -r requirements-linux.txt` 重试。

**Q2：MySQL 报 `Access denied for user 'root'@'localhost'`**
A：宝塔数据库 → root 密码 → 修改为强密码 → 同步更新 `.env` 的 `DATABASE_URL`。

**Q3：Redis 报 `NOAUTH`**
A：`.env` 的 `REDIS_PASSWORD` 与宝塔 Redis 配置的 `requirepass` 不一致。

**Q4：LLM 调用 401**
A：`.env` 的 `LLM_API_KEY` 错误或 DeepSeek 账户欠费。

**Q5：ChromaDB 报只读 / 权限错误**
A：`chown -R www:www memory/ && chmod -R 775 memory/`

**Q6：上传文件/笔记附件 404**
A：检查 `community_data/uploads/`、`note_data/` 目录是否存在且 `www` 用户可写。

**Q7：SSE 流式响应被 Nginx 缓冲**
A：Nginx 配置加 `proxy_buffering off;`（见 10.4）。

**Q8：Whisper 模型加载失败**
A：`models/` 目录未上传，或缺少 ffmpeg。`apt install ffmpeg` 后重试。

**Q9：跨域错误（前端控制台 CORS）**
A：`.env` 的 `ALLOWED_ORIGINS` 没加前端域名（多个用逗号分隔，无空格）。

**Q10：宝塔重启后服务未自启**
A：Python 项目管理器 → 项目设置 → 勾选「开机自启」。

---

## 十五、运维操作速查

```bash
# 重启服务（宝塔终端）
cd /www/wwwroot/all_tame_channel
# 方式1：宝塔面板内 Python 项目管理器 → 重启
# 方式2：直接kill
ps -ef | grep uvicorn
kill -9 <pid>

# 查看实时日志
tail -f /www/wwwlogs/你的域名.com.log        # Nginx
# 应用日志在 Python 项目管理器界面查看

# 更新代码
# 1. 本地重新打 deploy.tar
# 2. 宝塔文件管理器上传覆盖
# 3. 解压覆盖（注意备份 .env）
# 4. Python 项目管理器 → 重启项目

# 备份数据库
mysqldump -u root -p code_db > /backup/code_db_$(date +%Y%m%d).sql

# 备份用户上传数据
tar -czf /backup/user_data_$(date +%Y%m%d).tar.gz \
    memory note_data user_features user_voices community_data/uploads \
    wrong_answer_data recommendation_data
```
