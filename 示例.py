"""gduf-web-api 调用示例。

按需取消对应代码块的注释即可调用。将 SAVE_TO_FILE 改为 True 后，
所有已执行示例的结果会同时保存到 gduf_web_api_output.json。
"""

# ruff: noqa: RUF001, RUF002, RUF003 -- 中文内容有意使用全角标点。

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gduf_web_api as api

SAVE_TO_FILE = True
OUTPUT_FILE = Path("gduf_web_api_output.json")

_saved_results: dict[str, Any] = {}


def show_result(name: str, result: Any) -> None:
    """打印结果，并在开关打开时汇总保存为 JSON。"""
    print(f"==============={name}=============\n", result, "\n============================\n")

    if not SAVE_TO_FILE:
        return

    value = result.to_dict() if hasattr(result, "to_dict") else result
    _saved_results[name] = value
    OUTPUT_FILE.write_text(
        json.dumps(_saved_results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已保存到：{OUTPUT_FILE.resolve()}\n")


def main() -> None:
    """运行已取消注释的调用示例。"""
    with api.GdufClient(timeout=15, retries=2) as client:
        # 获取学院新闻
        news = api.get_ai_xyxw(page=1, client=client)
        show_result("学院新闻", news)

        # 获取学院新闻详情，传入 ArticleSummary 或详情 URL
        news_detail = api.get_ai_detail(news.items[0], client=client)
        show_result("学院新闻详情", news_detail)

        # 获取学术活动
        academic_activities = api.get_ai_xshuhd(page=1, client=client)
        show_result("学术活动", academic_activities)

        # 获取学生活动
        student_activities = api.get_ai_xshenghd(page=1, client=client)
        show_result("学生活动", student_activities)

        # 获取通知公告
        notices = api.get_ai_tzgg(page=1, client=client)
        show_result("通知公告", notices)

        # 获取首页四个栏目
        home = api.get_ai_home(client=client)
        show_result("学院首页", home)

        # 获取学院简介
        introduction = api.get_ai_xyjj(client=client)
        show_result("学院简介", introduction)

        # 获取机构设置
        organization = api.get_ai_jgsz(client=client)
        show_result("机构设置", organization)

        # 获取学院领导
        leaders = api.get_ai_xyld(page=1, client=client)
        show_result("学院领导", leaders)

        # 获取学院领导或其他人员详情，传入 PersonSummary
        leader_detail = api.get_ai_detail(leaders.items[0], client=client)
        show_result("学院领导详情", leader_detail)

        # 获取专任教师
        teachers = api.get_ai_zrjs(page=1, client=client)
        show_result("专任教师", teachers)

        # 获取教辅人员
        support_staff = api.get_ai_jfry(page=1, client=client)
        show_result("教辅人员", support_staff)

        # 获取计算机科学与技术专业介绍
        computer_science = api.get_ai_jsjkxyjs(client=client)
        show_result("计算机科学与技术", computer_science)

        # 获取软件工程专业介绍
        software_engineering = api.get_ai_rjgc(client=client)
        show_result("软件工程", software_engineering)

        # 获取数据科学与大数据技术专业介绍
        data_science = api.get_ai_sjkxydsjjs(client=client)
        show_result("数据科学与大数据技术", data_science)

        # 获取应用统计学专业介绍
        applied_statistics = api.get_ai_yytjx(client=client)
        show_result("应用统计学", applied_statistics)

        # 获取人工智能专业介绍
        artificial_intelligence = api.get_ai_rgzn(client=client)
        show_result("人工智能", artificial_intelligence)

        # 搜索站内信息
        search_results = api.search_ai("人工智能", page=1, client=client)
        show_result("搜索结果", search_results)


if __name__ == "__main__":
    main()
