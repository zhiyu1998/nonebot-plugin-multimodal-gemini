import asyncio
import os
import re
from pathlib import Path


async def remove_file(file_path):
    """异步删除单个文件"""
    try:
        await asyncio.to_thread(os.remove, file_path)  # 使用 asyncio.to_thread 异步删除文件
        print(f"已删除文件: {file_path}")
    except Exception as e:
        print(f"文件删除失败 {file_path}: {e}")


async def remove_all_files_in_dir(directory):
    """异步删除目录中的所有文件"""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        print(f"{directory} 不是一个目录")
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
        bool: 如果字符串中包含 HTTP/HTTPS 链接，返回 True；否则返回 False。
    """
    # 定义一个正则表达式模式，用于匹配 HTTP/HTTPS 链接
    pattern = r'http[s]?://\S+'

    # 使用 re.search 查找匹配项
    if re.search(pattern, input_string):
        return True
    return False
