# 学院教学小助手 · Backend

基于 **PydanticAI 2.x + FastAPI + DeepSeek（OpenAI 兼容）+ gduf-jwxt-api** 的后端骨架，已可运行。

## 目录结构

```text
backend/
  app/
    main.py                 # FastAPI 入口（健康检查、异常处理、CORS、路由挂载）
    config.py               # 环境变量配置（pydantic-settings）
    schemas/                # 统一响应结构、错误码、请求/响应模型
    api/                    # HTTP 路由：auth / chat / jwxt / knowledge
    services/
      session.py            # PostgreSQL 登录会话 + JwxtClient 进程缓存
    adapters/
      jwxt.py               # gduf-jwxt-api 适配层（异常映射、async 包装）
    agent/
      model_client.py       # DeepSeek OpenAI 兼容模型客户端
      prompts.py            # 系统提示词（含当前日期）
      tools.py              # 7 个 Agent 工具 + AgentDeps 依赖注入
      orchestrator.py       # Agent 构建与 run_chat 编排
    knowledge/
      service.py            # 文档加载/切片与统一检索门面（Chroma 向量/关键词兜底）
  data/
    knowledge/              # 知识库资料（.md/.txt/.json，示例数据待替换）
    information/            # 学院网站/竞赛资讯（示例数据待替换）
  tests/                    # pytest 测试（16 个，覆盖检索/接口/Agent）
```

## 安装

```powershell
cd back_end\backend
python -m venv .venv                       # 已创建可跳过
.venv\Scripts\python -m pip install -e ".[test]"
.venv\Scripts\python -m pip install -e ..\gduf-academic-api   # 本地学术资源接口包
```

`gduf-jwxt-api` 与 `gduf-web-api` 已声明为后端的 PyPI 运行依赖，会随第一条安装命令自动安装。

## 配置

复制 `.env.example` 为 `.env`，填写 `DEEPSEEK_API_KEY`、`DATABASE_URL` 和 `SESSION_ENCRYPTION_KEYS`。开发数据库可在项目根目录运行 `docker compose -f docker-compose.postgres.yml up -d`。未配置嵌入服务时知识库自动使用关键词检索。

## 运行

```powershell
# 启动后端（在 backend 目录下）
.venv\Scripts\python -m app.start --reload --port 8000
```

该入口会先执行 `alembic upgrade head`，迁移失败时不会启动 API。单独检查或执行迁移可运行 `.venv\Scripts\python -m alembic current` 和 `.venv\Scripts\python -m alembic upgrade head`。

- 健康检查：`GET /`
- 交互式接口文档：浏览器打开 `http://127.0.0.1:8000/docs`

## 测试

```powershell
.venv\Scripts\python -m pytest
```

## 主要接口

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/api/auth/captcha` | 获取验证码（返回 session_token + base64 图片） |
| POST | `/api/auth/login` | 学号/密码/验证码登录 |
| POST | `/api/auth/logout` | 退出并销毁会话 |
| GET | `/api/auth/status` | 查询登录状态 |
| POST | `/api/chat` | Agent 对话（必须登录，可传 `conversation_id`） |
| GET | `/api/conversations` | 当前学生的历史会话列表 |
| GET | `/api/conversations/{id}` | 分页读取历史消息 |
| DELETE | `/api/conversations/{id}` | 删除历史会话 |
| GET | `/api/schedule` | 个人课表 |
| GET | `/api/classroom-schedule` | 教室课表 |
| GET | `/api/grades` | 成绩列表与统计 |
| GET | `/api/grades/{index}/detail` | 单科成绩明细 |
| GET | `/api/training-plan` | 培养方案 |
| GET | `/api/knowledge/search` | 知识库检索 |
| GET | `/api/information/search` | 学院/竞赛资讯检索 |

登录后除 `/api/chat` 外的接口需携带请求头 `X-Session-Token: <session_token>`。

## 安全提醒

- `.env` 已被 `.gitignore` 忽略，真实密钥严禁提交。
- 曾出现在 `.env.example` 中的旧 DeepSeek Key 已清理，请到 DeepSeek 平台撤销该 Key 并重新生成。
