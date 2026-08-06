# gduf-web-api

广东金融学院公开网站的类型化 Python 客户端。首个来源是大数据与人工智能学院（`ai`）。

> 本项目是非官方客户端，与广东金融学院及其下属学院没有隶属关系。数据来自公开网页；网站结构变化可能导致解析失效。

## 安装

```bash
pip install gduf-web-api
```

需要 Python 3.10 或更高版本。

## 快速开始

```python
from gduf_web_api import get_ai_detail, get_ai_xyxw, search_ai

news = get_ai_xyxw(page=1)
print(news.total_items, news.total_pages)

first = news.items[0]
print(first.title, first.published_at, first.url)

detail = get_ai_detail(first)
print(detail.content_text)

results = search_ai("人工智能")
for item in results.items:
    print(item.title)
```

返回值是不可变 dataclass；`to_dict()` 会把日期和嵌套模型转换为 JSON 兼容值。

```python
import json
from gduf_web_api import get_ai_rgzn

major = get_ai_rgzn()
print(json.dumps(major.to_dict(), ensure_ascii=False))
```

## API

首页与动态栏目：

- `get_ai_home()`：一次请求解析首页的学院新闻、学术活动、学生活动和通知公告。
- `get_ai_xyxw(page=1)`：学院新闻。
- `get_ai_xshuhd(page=1)`：学术活动。
- `get_ai_xshenghd(page=1)`：学生活动。
- `get_ai_tzgg(page=1)`：通知公告。

学院概况：

- `get_ai_xyjj()`：学院简介。
- `get_ai_jgsz()`：机构设置。
- `get_ai_xyld(page=1)`：学院领导。
- `get_ai_zrjs(page=1)`：专任教师。
- `get_ai_jfry(page=1)`：教辅人员。

专业教学：

- `get_ai_jsjkxyjs()`：计算机科学与技术。
- `get_ai_rjgc()`：软件工程。
- `get_ai_sjkxydsjjs()`：数据科学与大数据技术。
- `get_ai_yytjx()`：应用统计学。
- `get_ai_rgzn()`：人工智能。

搜索与详情：

- `search_ai(keyword, page=1)`：AI 学院站内搜索。
- `get_ai_detail(item_or_url)`：接受 `ArticleSummary`、`PersonSummary`、相对 URL 或同域绝对 URL。

网页控制每页条目数，因此分页方法只接收从 1 开始的 `page`，不接收 `page_size`。

## 复用连接与异常

大量调用时应复用 `GdufClient`：

```python
from gduf_web_api import GdufClient, get_ai_xyxw, get_ai_zrjs

with GdufClient(timeout=15, retries=2) as client:
    news = get_ai_xyxw(client=client)
    teachers = get_ai_zrjs(client=client)
```

包内异常均继承 `GdufError`：

- `NetworkError`：连接、超时或 HTTP 错误。
- `ParseError`：网页结构不再符合已支持模板。
- `InvalidPageError`：页码不是正整数或超过栏目总页数。
- `UnsupportedSourceError`：请求了尚未注册的学院来源。

详情 URL 被限制在对应来源域名，避免把客户端用作任意 URL 请求器。

## 开发与扩展来源

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src/gduf_web_api
pytest
python -m build
twine check dist/*
```

网络请求、模型和异常由 `GdufClient` 共享；每个学院只实现内部来源适配器，并通过稳定的来源前缀便捷函数导出。新增来源不应修改现有 `get_ai_*` 行为。

## GitHub Actions 发布

仓库包含持续集成和 PyPI 发布工作流。发布前：

1. 在 TestPyPI/PyPI 的 Trusted Publishers 页面填写 GitHub owner、仓库名和工作流文件 `publish.yml`。
2. 分别填写 GitHub Environment `testpypi` 和 `pypi`；建议为正式 `pypi` 环境配置 required reviewers。
3. 手动运行 Publish workflow 会发布到 TestPyPI。
4. 更新 `pyproject.toml` 与 `gduf_web_api.__version__`，创建同版本 `vX.Y.Z` GitHub Release 后发布正式 PyPI。

工作流使用 GitHub OIDC 与短期凭据，不需要保存长期 PyPI API Token。首次发布前还应确认 `gduf-web-api` 名称在 PyPI 可用。

## License

[MIT](LICENSE)

