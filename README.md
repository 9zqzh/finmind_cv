# 学院教学小助手

面向广东金融学院学生的教学信息助手，整合教务查询、学院官网与竞赛信息、学术资源搜索、本地知识库、高德地图周边查询与出行路线规划，以及基于 PydanticAI 的自然语言对话。系统包含 React 前端、FastAPI 后端、PostgreSQL 持久化，并可选接入 Chroma 向量检索（混合检索）；另内置模型操作手册（Playbook）模块，为高频问题沉淀固定最优路径并支持半自动进化。

## 项目结构

```text
.
├── frontend/                   # React + Vite 前端
├── backend/                    # FastAPI、Agent、迁移、数据与测试
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

配置完整时启用**混合检索**：向量（Chroma）与关键词双路召回后按 RRF 融合排序，任一路径失败（如嵌入接口超时、配额耗尽）自动降级到另一路，单次故障不会永久关闭向量检索。可通过以下变量调参（均可在 `.env` 覆盖）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `KNOWLEDGE_VECTOR_MIN_SCORE` | `0.5` | 向量分数阈值，仅过滤语义明显无关项 |
| `KNOWLEDGE_VECTOR_CONFIDENCE_MIN` | `0.75` | 关键词零命中时向量结果的置信门槛，低于该值视为未检索到 |
| `KNOWLEDGE_VECTOR_TOP_K` | `20` | 混合检索时向量/关键词各自召回的候选数 |
| `EMBEDDING_RETRIES` | `2` | 嵌入请求失败时的指数退避重试次数 |

### 4. 可选地图查询（高德）

在 `.env` 中填写高德开放平台（https://lbs.amap.com ，免费）申请的 Web 服务 Key 后，即可在 AI 对话中使用周边地点查询与路线规划：

```dotenv
AMAP_API_KEY=你的高德Web服务Key
# 可选：百度地图开放平台 Key，用于补充地点点评数与评分
BAIDU_MAP_API_KEY=
```

支持的功能：

- **周边地点查询**：搜索美食、景点、娱乐等（如“学校周边有什么好吃的”），返回名称、地址、电话、星级评分、人均消费、距中心距离（高德返回照片时附带门店首图），前端以卡片展示并附高德导航链接；
- **出行路线规划**：步行 / 驾车 / 骑行 / 公交四种方式，返回距离、预计耗时与导航链接；
- **默认起点**为广东金融学院清远校区（可用 `AMAP_DEFAULT_ORIGIN` 修改，`AMAP_DEFAULT_LOCATION` 可配置兜底坐标，`AMAP_SEARCH_RADIUS` 配置周边搜索半径，默认 5000 米）。

回答中的地点与路线会以**引用卡片**展示：工具返回结果时后端为每个地点/路线生成 `citation_ref`（`c1`、`c2`…），模型在正文中用 `<citation ref="cN">参考来源：地点或路线名称</citation>` 标签引用，前端将其原位渲染为可点击的地图卡片（评分、人均消费、点评数、距离、地址/路线耗时与导航按钮），卡片链接仅接受高德官方域名，未配置或未知引用自动降级为普通文字。

未配置 Key 时，Agent 会如实提示地图功能不可用，不影响其他功能。高德免费接口仅提供星级评分与人均消费，不包含顾客评论文本；配置 `BAIDU_MAP_API_KEY` 后可补充地点点评数。

### 5. 模型操作手册（Playbook）与自进化

操作手册是把高频问题的固定最优路径沉淀为 Markdown 文件（`backend/data/playbooks/`，frontmatter 声明 `title`/`keywords`/`source`），用户提问命中关键词时，该路径以动态指令注入本轮对话，让模型按预先验证过的稳定步骤组织工具调用与回答。

- **热加载**：目录内文件的新增、修改、删除会在下次匹配时自动生效，无需重启服务；
- **自动生成**：系统按周自动分析高频提问簇，调用大模型总结成草稿（也可在管理台手动触发）；
- **人工审核**：管理员在 `/admin` 管理台浏览器中审核草稿，通过后立即转为正式手册（操作步骤见 [docs/管理台审核操作指南.md](docs/管理台审核操作指南.md)）。

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
cd backend
.venv\Scripts\python -m app.start --reload --port 8000
```

根目录 `.env` 同样适用于本地后端。本地模式需要可从宿主机访问的 PostgreSQL，并将 `DATABASE_URL` 指向它；更推荐直接使用完整 Docker 编排。后端启动器会先执行 Alembic 迁移，再启动 Uvicorn。若本机 8000 端口被其他进程占用，可改用其他端口（如 `--port 8001`），并同步修改 `frontend/vite.config.ts` 中的 `/api` 代理 target。

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
| `EMBEDDING_*` | 向量嵌入服务配置（含 `EMBEDDING_RETRIES` 重试次数） |
| `KNOWLEDGE_RETRIEVAL_MODE` | `auto` 或 `keyword` |
| `KNOWLEDGE_VECTOR_MIN_SCORE` | 向量分数阈值，默认 `0.5` |
| `KNOWLEDGE_VECTOR_CONFIDENCE_MIN` | 关键词零命中时向量置信门槛，默认 `0.75` |
| `KNOWLEDGE_VECTOR_TOP_K` | 混合检索候选数，默认 `20` |
| `AMAP_*` | 高德地图配置（Key、默认起点、搜索半径），见上文地图小节 |
| `BAIDU_MAP_API_KEY` | 可选：百度地图 Key，补充地点点评数 |
| `PLAYBOOK_DIR` | 操作手册目录，默认 `data/playbooks` |
| `PLAYBOOK_DRAFT_DIR` | 自进化草稿目录，默认 `data/playbook_drafts` |
| `EVOLUTION_*` | 自进化流水线配置（聚类阈值、窗口、冷却期、定时开关等） |
| `INITIAL_ADMIN_STUDENT_NUMBER` | 管理后台初始管理员学号；留空时后台禁用 |
| `FINDPAPERS_DATABASES` | 启用的学术源，默认 `arxiv,pubmed,semantic_scholar`；OpenAlex/IEEE/Scopus/WoS 启用时需对应 Token |
| `FINDPAPERS_REQUEST_TIMEOUT_SECONDS` / `FINDPAPERS_SEARCH_TIMEOUT_SECONDS` | 单请求/整次聚合搜索超时，默认 `10` / `30` 秒 |
| `FINDPAPERS_MAX_RETRIES` / `FINDPAPERS_RATE_LIMIT_RETRIES` | 普通/限流重试次数，默认 `1` / `0` |
| 其他 `FINDPAPERS_*` | 学术平台代理、SSL、联系邮箱及各数据库 API Token |

## 测试与构建

```powershell
# 后端
backend\.venv\Scripts\python -m pytest backend\tests

# 前端
cd frontend
npm test
npm run build
```

## 数据与安全

- `backend/data/knowledge/` 与 `backend/data/information/` 是可检索的结构化资料；`resources/` 保存原始 PDF、Word、Excel 等文件。
- 教务密码和验证码不会持久化；登录 Cookie 加密后存入 PostgreSQL，数据库中只保存会话令牌摘要。
- 管理后台复用用户登录会话；管理员授权、登录结果、草稿审核和对话详情访问写入结构化审计日志。
- 前端和 API 通过 Nginx 同源访问；SSE 流式对话已关闭代理缓冲。
- `docker compose down` 不删除命名卷；只有显式添加 `-v` 才会删除持久化数据。

## 进一步阅读

- [后端说明](backend/README.md)
- [项目结构说明](docs/项目结构说明.md)
- [技术栈说明](docs/技术栈说明.md)
- [业务功能说明](docs/业务功能说明.md)
- [团队本地运行与向量检索指南](docs/团队本地运行与向量检索指南.md)
- [管理台审核操作指南](docs/管理台审核操作指南.md)
- [Findpapers 上游文档](https://github.com/jonatasgrosman/findpapers)
