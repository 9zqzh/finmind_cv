# gduf-academic-api

学术资源聚合检索客户端：对接 arXiv、Semantic Scholar 等无反爬、开放获取的学术平台。

## 安装

在 backend 虚拟环境中以可编辑模式安装：

```powershell
cd back_end\backend
.\.venv\Scripts\python -m pip install -e ../gduf-academic-api
```

## 用法

```python
from academic_api import AcademicClient

with AcademicClient(proxy=None) as client:
    result = client.search("transformer attention", max_results=5)
    for item in result.items:
        print(item.title, item.url, item.pdf_url)
```

## 扩展平台

在 `src/academic_api/platforms/` 下新建模块，继承 `BasePlatform` 并使用 `@register` 装饰即可，注册表会自动发现：

```python
from academic_api.platforms import register
from academic_api.platforms.base import BasePlatform

@register
class MyPlatform(BasePlatform):
    name = "my_platform"
    display_name = "My Platform"

    def search(self, query, max_results=10):
        ...
```

## 已接入平台

| 平台 | 标识 | 说明 |
|------|------|------|
| arXiv | `arxiv` | CS/AI 预印本，全文开放获取，Atom XML API |
| Semantic Scholar | `semantic_scholar` | 跨学科论文检索，含引用数与 OA PDF，JSON API |
