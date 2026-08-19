# 学院教学小助手

面向广东金融学院学生的教学信息助手，整合教务查询、学院官网与竞赛信息、学术资源搜索、本地知识库以及基于 PydanticAI 的自然语言对话。系统包含 React 前端、FastAPI 后端、PostgreSQL 持久化，并可选接入 Chroma 向量检索。

## 项目结构

```text
.
├── frontend/                   # React + Vite 前端
├── backend/                    # FastAPI、Agent、迁移、数据与测试
├── packages/gduf-academic-api/ # 学术资源聚合客户端
├── scripts/                    # 资料转换等维护脚本
├── resources/                  # 可浏览、下载的原始资料
├── docs/                       # 需求、架构和开发文档
├── compose.yaml                # 完整容器编排
└── .env.example                # 统一配置模板
```

## Docker 一键启动

### 1. 首次安全初始化

需要 Docker Desktop（或其他支持 Compose v2 的 Docker 环境）。在项目根目录执行：

```powershell
Copy-Item .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

打开 `.env`：

- 为 `POSTGRES_PASSWORD` 设置仅包含 URL 安全字符的强密码；
- 将上一条命令生成的值填入 `SESSION_ENCRYPTION_KEYS`；
- 需要 AI 对话时填写 `DEEPSEEK_API_KEY`，其余功能不依赖该密钥。

真实 `.env` 已被 Git 与 Docker 构建上下文忽略，禁止提交。如果从旧目录升级，请把原 `back_end/backend/.env` 中仍需使用的配置复制到根目录 `.env`。

### 2. 启动完整应用

```powershell
docker compose up --build -d
```

等待健康检查完成后访问：

- Web 应用：<http://localhost:8080>
- API 文档：<http://localhost:8080/docs>
- 存活检查：<http://localhost:8080/healthz>

可在 `.env` 中修改 `APP_PORT`，例如 `APP_PORT=9000`。PostgreSQL 和后端默认只在 Compose 内部网络开放，不占用宿主机端口。

常用维护命令：

```powershell
docker compose ps
docker compose logs -f backend
docker compose down
docker compose down -v  # 同时删除数据库和 Chroma 数据，请谨慎使用
```

### 3. 可选向量检索

默认不启动 Chroma，知识库使用关键词检索。先在 `.env` 中配置 `EMBEDDING_BASE_URL`、`EMBEDDING_API_KEY` 和 `EMBEDDING_MODEL`，再执行：

```powershell
docker compose --profile vector up --build -d
```

后端会通过 Compose 服务名 `chroma:8000` 连接向量数据库；未启动 Profile 或嵌入配置不完整时会自动回退到关键词检索。

## GitHub Release 自动部署

普通分支推送和 Pull Request 只运行前后端测试，不构建或发布 Docker 镜像。只有在 GitHub 仓库的 Releases 页面创建并发布 Release 后，`.github/workflows/ci-cd.yml` 才会：

1. 为前端和后端构建 Docker 镜像；
2. 将镜像推送到阿里云 ACR 的 `liangjz1/finmind` 私有仓库；
3. 使用发行标签、提交 SHA 和 `latest` 分别标记镜像；
4. 通过 SSH 上传 `compose.prod.yaml`，并让服务器拉取本次发行提交对应的镜像。

服务器需要预先创建 `~/finmind/.env`，其中包含普通运行配置以及镜像拉取地址：

```dotenv
# 广州同 VPC 的阿里云 ECS 使用专有网络地址；其他服务器使用公网地址。
ACR_PULL_REGISTRY=crpi-q46i31ygwyvi127o-vpc.cn-guangzhou.personal.cr.aliyuncs.com
IMAGE_TAG=latest
```

服务器还需要使用对应的公网或专有网络域名执行一次 `docker login`。GitHub Actions 需要配置 `ACR_USERNAME`、`ACR_PASSWORD`、`SSH_HOST`、`SSH_PORT`、`SSH_USER`、`SSH_PRIVATE_KEY` 和 `SSH_KNOWN_HOSTS` Secrets。

## 非 Docker 本地开发

### 后端

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install --upgrade pip
backend\.venv\Scripts\python -m pip install -e ".\backend[test]"
backend\.venv\Scripts\python -m pip install -e .\packages\gduf-academic-api
cd backend
.venv\Scripts\python -m app.start --reload --port 8000
```

根目录 `.env` 同样适用于本地后端。本地模式需要可从宿主机访问的 PostgreSQL，并将 `DATABASE_URL` 指向它；更推荐直接使用完整 Docker 编排。后端启动器会先执行 Alembic 迁移，再启动 Uvicorn。

### 前端

```powershell
cd frontend
npm ci
npm run dev
```

访问 <http://localhost:5173>。Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 配置说明

配置集中在根目录 `.env`，完整字段见 [`.env.example`](.env.example)。主要变量：

| 变量 | 用途 |
| --- | --- |
| `APP_PORT` | Nginx 对外端口，默认 `8080` |
| `POSTGRES_DB/USER/PASSWORD` | Compose PostgreSQL 配置 |
| `SESSION_ENCRYPTION_KEYS` | 登录 Cookie 的 Fernet 加密密钥，必填 |
| `DEEPSEEK_*` | OpenAI 兼容模型配置 |
| `EMBEDDING_*` | 向量嵌入服务配置 |
| `KNOWLEDGE_RETRIEVAL_MODE` | `auto` 或 `keyword` |
| `ACADEMIC_PROXY` | arXiv、Semantic Scholar 等平台的可选代理 |

## 测试与构建

```powershell
# 后端
backend\.venv\Scripts\python -m pytest backend\tests

# 内部学术包
backend\.venv\Scripts\python -m pytest packages\gduf-academic-api\tests -o addopts=""

# 前端
cd frontend
npm test
npm run build
```

## 数据与安全

- `backend/data/knowledge/` 与 `backend/data/information/` 是可检索的结构化资料；`resources/` 保存原始 PDF、Word、Excel 等文件。
- 教务密码和验证码不会持久化；登录 Cookie 加密后存入 PostgreSQL，数据库中只保存会话令牌摘要。
- 前端和 API 通过 Nginx 同源访问；SSE 流式对话已关闭代理缓冲。
- `docker compose down` 不删除命名卷；只有显式添加 `-v` 才会删除持久化数据。

## 进一步阅读

- [后端说明](backend/README.md)
- [项目结构说明](docs/项目结构说明.md)
- [技术栈说明](docs/技术栈说明.md)
- [业务功能说明](docs/业务功能说明.md)
- [团队本地运行与向量检索指南](docs/团队本地运行与向量检索指南.md)
- [学术资源客户端说明](packages/gduf-academic-api/README.md)
