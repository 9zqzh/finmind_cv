# gduf-web-api

广东金融学院公开网站的类型化 Python 客户端。当前支持大数据与人工智能学院官网（`ai`）和学院竞赛管理与问答平台（`aijspt`）。

> 本项目是非官方客户端，与广东金融学院及其下属学院没有隶属关系。数据来自公开网页；网站结构变化可能导致解析失效。

## 安装

```bash
pip install gduf-web-api
```

需要 Python 3.10 或更高版本。

仓库根目录的 [`示例.py`](示例.py) 包含学院官网和竞赛平台的完整调用示例。

## 快速开始

```python
from gduf_web_api import get_ai_detail, get_ai_xyxw, get_aijspt_bslb, search_ai

news = get_ai_xyxw(page=1)
print(news.total_items, news.total_pages)

first = news.items[0]
print(first.title, first.published_at, first.url)

detail = get_ai_detail(first)
print(detail.content_text)

results = search_ai("人工智能")
for item in results.items:
    print(item.title)

competitions = get_aijspt_bslb(year=2026, status="registration_open")
for competition in competitions.items:
    print(competition.title, competition.registration_end_at)
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

竞赛平台（`aijspt`）：

- `get_aijspt_bslb(year=None, status=None, category=None, department=None, keyword=None)`：比赛列表；筛选条件同时生效，结果保持平台排序。
- `get_aijspt_bsxq(competition_or_id)`：比赛详情；接受 `CompetitionSummary`、比赛 UUID、相对路径或同域绝对 URL。
- `get_aijspt_tzgg(limit=20)`：公开通知公告。
- `get_aijspt_stlb()`：五大竞赛社团概览。

### 可输入参数

| 适用接口 | 参数 | 类型 | 默认值 | 可输入值与说明 |
| --- | --- | --- | --- | --- |
| `get_ai_xyxw`、`get_ai_xshuhd`、`get_ai_xshenghd`、`get_ai_tzgg`、`get_ai_xyld`、`get_ai_zrjs`、`get_ai_jfry` | `page` | `int` | `1` | 从 `1` 开始的正整数；最大页数由网站决定，超出范围抛出 `InvalidPageError`。 |
| `search_ai` | `keyword` | `str` | 必填 | 非空搜索词；前后空白会被移除。 |
| `search_ai` | `page` | `int` | `1` | 从 `1` 开始的搜索结果页码。 |
| `get_ai_detail` | `item_or_url` | `ArticleSummary | PersonSummary | str` | 必填 | 可传列表结果对象、AI 学院站内相对 URL，或 `https://ai.gduf.edu.cn/` 同域绝对 URL。 |
| `get_aijspt_bslb` | `year` | `int | None` | `None` | 比赛年份正整数，例如 `2026`；`None` 表示不限年份。 |
| `get_aijspt_bslb` | `status` | `str | None` | `None` | `registration_open`、`previous_recording`、`upcoming`、`in_progress` 或 `finished`；`None` 表示不限状态。 |
| `get_aijspt_bslb` | `category` | `str | None` | `None` | 按平台分类原文精确匹配，例如 `"软件设计类"`、`"计算机类"`；`None` 表示不限分类。 |
| `get_aijspt_bslb` | `department` | `str | None` | `None` | 按归属学院原文精确匹配，例如 `"大数据与人工智能学院"`；`None` 表示不限学院。 |
| `get_aijspt_bslb` | `keyword` | `str | None` | `None` | 在比赛标题和摘要中进行不区分大小写的包含匹配；不能传空字符串。 |
| `get_aijspt_bsxq` | `competition_or_id` | `CompetitionSummary | str` | 必填 | 可传比赛列表对象、UUID、`/competitions/{UUID}` 相对路径，或 `https://ai-data-competitions.cn/competitions/{UUID}` 同域绝对 URL。 |
| `get_aijspt_tzgg` | `limit` | `int` | `20` | 要请求的通知数量，必须为正整数。 |
| 所有 `get_ai_*`、`search_ai` 和 `get_aijspt_*` 便捷函数 | `client` | `GdufClient | None` | `None` | 仅限关键字传入；复用已有客户端可共享连接。省略时函数会自动创建并关闭客户端。 |

`get_aijspt_bslb` 的多个筛选参数使用 AND 关系，即返回同时满足所有已传条件的比赛，并保持平台原始排序。`None` 表示不启用对应筛选。

竞赛状态使用平台原始值，包括 `registration_open`（报名中）、`previous_recording`（往期比赛补录中）、`upcoming`（即将开始）、`in_progress`（进行中）和 `finished`（已结束）。平台时间解析为带时区的 `datetime`，列表接口无分页，返回 `ListResult`。

```python
from gduf_web_api import get_aijspt_bslb, get_aijspt_bsxq

competitions = get_aijspt_bslb(category="软件设计类", keyword="软件杯")
detail = get_aijspt_bsxq(competitions.items[0])

print(detail.description_text)
for phase in detail.timeline:
    print(phase.date, phase.label, phase.description)
```

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

网络请求、模型和异常由 `GdufClient` 共享；学院官网来源与竞赛信息来源使用各自的内部适配器协议，并通过稳定的来源前缀便捷函数导出。新增来源不应修改现有 `get_ai_*` 或 `get_aijspt_*` 行为。

## GitHub Actions 发布

仓库包含持续集成和 PyPI 发布工作流。发布前：

1. 在 TestPyPI/PyPI 的 Trusted Publishers 页面填写 GitHub owner、仓库名和工作流文件 `publish.yml`。
2. 分别填写 GitHub Environment `testpypi` 和 `pypi`；建议为正式 `pypi` 环境配置 required reviewers。
3. 手动运行 Publish workflow 会发布到 TestPyPI。
4. 更新 `pyproject.toml` 与 `gduf_web_api.__version__`，创建同版本 `vX.Y.Z` GitHub Release 后发布正式 PyPI。

工作流使用 GitHub OIDC 与短期凭据，不需要保存长期 PyPI API Token。首次发布前还应确认 `gduf-web-api` 名称在 PyPI 可用。

## License

[MIT](LICENSE)
