# 学院教学小助手 Backend

FastAPI 后端负责教务会话、PostgreSQL 持久化、PydanticAI Agent、知识检索以及公开信息适配。

## 目录

```text
backend/
├── app/          # 应用、路由、服务、Agent 与适配层
├── data/         # 知识库和资讯数据
├── migrations/   # Alembic 迁移
├── tests/        # pytest 测试
├── alembic.ini
└── pyproject.toml
```

## 本地安装与运行

在仓库根目录创建统一环境配置 `.env`，然后执行：

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install -e ".\backend[test]"
backend\.venv\Scripts\python -m pip install -e .\packages\gduf-academic-api
cd backend
.venv\Scripts\python -m app.start --reload --port 8000
```

启动入口会先执行 `alembic upgrade head`，迁移失败时不会启动 API。生产式启动、数据库和环境变量配置见仓库根目录 [README](../README.md)。

## 测试

```powershell
backend\.venv\Scripts\python -m pytest backend\tests
```

资源转换工具位于 `scripts/convert_resources.py`；安装 `backend[tools]` 可获得 PDF、Word 和 Excel 转换依赖。
