# PydanticAI 安装指南（学院教学小助手）

> 适用环境：Windows + Python 3.10+（本项目使用 Python 3.12）
> 参考版本：PydanticAI 2.0（2026-06 稳定版）
> 更新时间：2026-08-05

---

## 一、前置条件

- Python 3.10+（建议 3.12）
- `pip`（Python 自带）
- 可访问 PyPI 的网络（国内网络慢时可配置清华镜像，见"常见问题"）
- DeepSeek API Key（在 [DeepSeek 开放平台](https://platform.deepseek.com) 创建）

---

## 二、安装步骤

### 方式 A：作为本项目后端依赖安装（推荐）

在项目 `backend` 目录下执行：

```powershell
cd C:\Users\14712\Desktop\学院教学小助手\backend

# 1. 创建虚拟环境（已创建过可跳过）
python -m venv .venv

# 2. 安装项目依赖（含 pydantic-ai、pydantic-settings、pytest）
.venv\Scripts\python -m pip install -e ".[test]"
```

`pyproject.toml` 已声明 `pydantic-ai>=1.0,<3`，安装时会解析为当前最新稳定版（2.x）。

### 方式 B：独立安装（不依赖本项目）

```powershell
# 完整安装（含 OpenAI/Anthropic/Google 模型、CLI、MCP、Logfire 等）
pip install pydantic-ai

# 最小安装（仅 OpenAI 兼容接口，够本项目用）
pip install "pydantic-ai-slim[openai]"
```

### 方式 C：使用 uv（可选，更快）

```powershell
uv add pydantic-ai
```

---

## 三、验证安装

```powershell
.venv\Scripts\python -c "import importlib.metadata as m; print(m.version('pydantic-ai'))"
```

输出 `2.x` 即安装成功。

---

## 四、配置 DeepSeek

项目已提供 `.env.example`，复制为 `.env` 并填入密钥：

```powershell
Copy-Item .env.example .env
```

`.env` 内容：

```env
DEEPSEEK_API_KEY=sk-你的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

注意事项：

- `.env` 已被 `backend/.gitignore` 忽略，严禁提交到 Git。
- 密钥泄露后请立即到 DeepSeek 平台撤销并重新生成。
- 模型名按当前可用模型填写（本项目默认 `deepseek-v4-flash`）。

---

## 五、最小示例

新建 `backend/quick_start.py`：

```python
import asyncio

from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider


async def main() -> None:
    client = AsyncOpenAI(
        base_url="https://api.deepseek.com/v1",
        api_key="sk-你的密钥",  # 建议改为读取环境变量
    )
    model = OpenAIChatModel(
        "deepseek-v4-flash",
        provider=OpenAIProvider(openai_client=client),
    )
    agent = Agent(model, system_prompt="你是学院教学小助手。")

    result = await agent.run("你好，请介绍一下你自己")
    print(result.output)


if __name__ == "__main__":
    asyncio.run(main())
```

运行：

```powershell
.venv\Scripts\python quick_start.py
```

> 说明：PydanticAI 2.0 官方还内置了 `DeepSeekProvider`（`pydantic_ai.providers.deepseek`），可直接按名称使用；上面的 OpenAI 兼容写法（`OpenAIChatModel` + 自定义 `AsyncOpenAI` 客户端）在任何版本都稳定可用。具体以安装后 `pydantic_ai` 版本文档为准。

---

## 六、运行测试

```powershell
.venv\Scripts\python -m pytest
```

---

## 七、常见问题

| 问题 | 解决 |
| --- | --- |
| `python` 命令找不到 | 使用 Python 完整路径，或把 Python 加入 PATH |
| 安装慢/超时 | 使用清华镜像：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "pydantic-ai"` |
| v1 老代码报错 | 2.0 采用 capabilities/harness 设计，参考官方 [升级指南](https://pydantic.dev/docs/ai/project/changelog/) 调整 |
| API Key 被提交到 Git | 立即从 Git 历史中移除并到平台撤销密钥；密钥只放 `.env` |

---

## 八、参考链接

- 官方安装文档：<https://pydantic.dev/docs/ai/install/>
- OpenAI 兼容模型文档：<https://pydantic.dev/docs/ai/models/openai/>
- DeepSeek 开放平台：<https://platform.deepseek.com>

---

## 九、本项目当前状态（2026-08-05）

- `backend/.venv` 虚拟环境已创建，`pydantic-ai 2.24`、`fastapi`、`uvicorn`、`pytest`、`pydantic-settings`、`openai` 等依赖已全部安装就位，`jwxtapi` 教务包已以可编辑模式装入。
- 后端骨架已搭建完成并实测通过，运行 `.venv\Scripts\python -m pytest` 应有 16 个测试全部通过。
- 后续开发请阅读《docs/后端后续开发操作指南.md》。
