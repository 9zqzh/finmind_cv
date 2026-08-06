"""gduf-web-api 基本调用示例。"""

# ruff: noqa: RUF001 -- 中文输出有意使用全角标点。

from gduf_web_api import (
    GdufClient,
    get_ai_detail,
    get_ai_rgzn,
    get_ai_xyjj,
    get_ai_xyxw,
    get_ai_zrjs,
    search_ai,
)


def main() -> None:
    """读取学院新闻、教师、专业和搜索结果。"""
    with GdufClient(timeout=15, retries=2) as client:
        news = get_ai_xyxw(page=1, client=client)
        print(f"学院新闻：共 {news.total_items} 条，{news.total_pages} 页")
        for item in news.items[:3]:
            print(f"- {item.published_at} {item.title}")

        if news.items:
            detail = get_ai_detail(news.items[0], client=client)
            print(f"\n最新新闻正文：{detail.title}")
            print(detail.content_text[:200], "...")

        teachers = get_ai_zrjs(client=client)
        print(f"\n专任教师：共 {teachers.total_items} 人")
        for teacher in teachers.items[:3]:
            print(f"- {teacher.name}（{teacher.role or '职称未注明'}）")

        introduction = get_ai_xyjj(client=client)
        print(f"\n学院简介：{introduction.content_text[:100]} ...")

        major = get_ai_rgzn(client=client)
        print(f"\n专业介绍：{major.title}")
        print(major.content_text[:100], "...")

        results = search_ai("人工智能", client=client)
        print(f"\n搜索“人工智能”：共 {results.total_items} 条")
        for item in results.items[:3]:
            print(f"- {item.title}")


if __name__ == "__main__":
    main()
