import asyncio
import os
import re
from pathlib import Path
from urllib.parse import quote

from nonebot import logger
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.content_filter_strategy import BM25ContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

async def remove_file(file_path):
    """异步删除单个文件"""
    try:
        await asyncio.to_thread(os.remove, file_path)  # 使用 asyncio.to_thread 异步删除文件
        logger.info(f"已删除文件: {file_path}")
    except Exception as e:
        logger.info(f"文件删除失败 {file_path}: {e}")


async def remove_all_files_in_dir(directory):
    """异步删除目录中的所有文件"""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        logger.info(f"{directory} 不是一个目录")
        return

    tasks = []
    for file_path in dir_path.iterdir():
        if file_path.is_file():
            tasks.append(remove_file(file_path))  # 为每个文件创建一个异步任务

    await asyncio.gather(*tasks)  # 并发执行所有任务


def contains_http_link(input_string):
    """
    检查输入的字符串中是否包含 HTTP 或 HTTPS 链接。

    参数:
        input_string (str): 要检查的字符串。

    返回值:
        str: 如果字符串中包含 HTTP/HTTPS 链接，返回 url；否则返回 ""。
    """
    # 定义一个正则表达式模式，用于匹配 HTTP/HTTPS 链接
    pattern = r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+'

    # 使用 re.search 查找匹配项
    url = re.search(pattern, input_string)
    if url:
        return url.group()
    return ""


async def crawl_url_content(url: str) -> str:
    async with AsyncWebCrawler(
            browser_type="chromium",
            verbose=True,
            headless=True,
    ) as crawler:
        try:
            result = await crawler.arun(
                url=url,
                cach_mode=CacheMode.ENABLED,
                markdown_generator=DefaultMarkdownGenerator(
                    content_filter=BM25ContentFilter(user_query=None, bm25_threshold=1.5)
                ),
                exclude_external_images=True,
                excluded_tags=['script', 'style', 'iframe', 'form', 'nav']
            )
            if result.success:
                return result.markdown_v2.raw_markdown
            else:
                return "爬取失败，无法获取页面内容。"
        except Exception as e:
            return f"爬取过程中发生错误：{str(e)}"


async def crawl_search_keyword(keyword: str) -> str:
    safe_keyword = quote(keyword.replace("搜索", ""))
    search_url = f"https://www.baidu.com/s?wd={safe_keyword}"
    async with AsyncWebCrawler(
            browser_type="chromium",
            verbose=True,
            headless=True,
    ) as crawler:
        try:
            result = await crawler.arun(
                url=search_url,
                cach_mode=CacheMode.DISABLED,
                markdown_generator=DefaultMarkdownGenerator(
                    content_filter=BM25ContentFilter(user_query=keyword, bm25_threshold=1.0)
                ),
                exclude_external_images=True,
                excluded_tags=['script', 'style', 'iframe', 'form', 'nav']
            )
            if result.success:
                return result.markdown_v2.raw_markdown
            else:
                return "搜索失败，无法获取相关结果。"
        except Exception as e:
            return f"搜索过程中发生错误：{str(e)}"