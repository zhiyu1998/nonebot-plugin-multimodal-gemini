import base64
import mimetypes
import os
from pathlib import Path
from typing import Dict, List  # noqa: UP035
from urllib.parse import quote

import aiofiles
import google.generativeai as genai
import httpx
from nonebot import get_plugin_config, on_command, require
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageEvent
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import is_type

from .utils import contains_http_link, crawl_search_keyword, crawl_url_content, remove_all_files_in_dir

require("nonebot_plugin_localstore")

import nonebot_plugin_localstore as store

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

from .config import Config

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="谷歌 Gemini 多模态助手",
    description="Nonebot2 的谷歌 Gemini 多模态助手，一个命令即可玩转 Gemini 的多模态！",
    usage=(
        "指令：\n"
        "(1) 多模态助手：[引用文件(可选)] + gemini + [问题(可选)]\n"
        "(2) llama搜索：gemini + 搜索[问题]\n\n"
        "支持引用的文件格式有：\n"
        "  音频: .wav, .mp3, .aiff, .aac, .ogg, .flac\n"
        "  图片: .png, .jpeg, .jpg, .webp, .heic, .heif\n"
        "  视频: .mp4, .mpeg, .mov, .avi, .flv, .mpg, .webm, .wmv, .3gpp\n"
        "  文档: .pdf, .js, .py, .txt, .html, .htm, .css, .md, .csv, .xml, .rtf"
    ),
    type="application",
    homepage="https://github.com/zhiyu1998/nonebot-plugin-multimodal-gemini",
    config=Config,
    supported_adapters={"~onebot.v11"},
)

# 加载配置
plugin_config = get_plugin_config(Config)

# 配置 Google Generative AI
API_KEY = plugin_config.gm_api_key
MODEL_NAME = plugin_config.gm_model
PROMPT = plugin_config.gm_prompt

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# 注册指令
gemini = on_command("gemini", aliases={"Gemini"}, priority=5, rule=is_type(GroupMessageEvent), block=True)


# 处理多模态内容或文本问题
@gemini.handle()
async def chat(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    query = args.extract_plain_text().strip()
    file_list, text_data = await auto_get_url(bot, event)
    # logger.info(f"引用文件列表{file_list}，引用文字内容{text_data}")
    # 如果有文字则将文字内容加入query
    if text_data:
        query += f"引用：{text_data}"
    if file_list:
        completion: str = await fetch_gemini_req(query, file_list)
        await gemini.finish(Message(completion), reply_message=True)
    # 如果只是文字
    if query.startswith("搜索"):
        if plugin_config.gm_search and MODEL_NAME == "gemini-2.0-flash-exp":
            completion: str = await gemini_search_extend(query)
            await gemini.finish(Message(completion), reply_message=True)
        search_ans = await crawl_search_keyword(query)
        query = f"用户的问题是：{query}，以下是用户关键词的搜索结果：\n{search_ans}"
    elif url := contains_http_link(query):
        url_ans = await crawl_url_content(url)
        query = f"用户的问题是：{query}，以下是用户提供的链接内容摘要：\n{url_ans}"
    completion: str = await fetch_gemini_req(query)
    await gemini.finish(Message(completion), reply_message=True)


async def auto_get_url(bot: Bot, event: MessageEvent):
    # 判断是否存在回复
    reply = event.reply
    file_list = []
    text_data = ""
    if reply:
        # logger.info(reply)
        for segment in reply.message:
            msg_type = segment.type  # 消息类型
            msg_data = segment.data  # 消息内容
            # 根据消息类型处理
            if msg_type in ["image", "audio", "video"]:
                url = msg_data.get("url") or msg_data.get("file_url")  # 提取视频或图片的 URL
                file_id = msg_data.get("file") or msg_data.get("file_id")
                # 将文件转换为base64
                local_path = await download_file(url, msg_type, file_id)  # type: ignore
                file_data = await to_gemini_init_data(local_path)
                file_list.append(file_data)
            elif msg_type == "file":
                file_id = msg_data.get("file_id")
                file_url_info = await bot.call_api(
                    "get_group_file_url",
                    file_id=file_id,
                    group_id=event.group_id,  # type: ignore
                )  # 提取文件的 URL
                url = file_url_info["url"]
                # 将文件转换为base64
                local_path = await download_file(url, msg_type, file_id)  # type: ignore
                file_data = await to_gemini_init_data(local_path)
                file_list.append(file_data)
            elif msg_type == "forward":
                for forward_segment in msg_data.get("content"):  # type: ignore
                    for content_segment in forward_segment.get("message"):
                        msg_type_segment = content_segment.get("type")
                        msg_data_segment = content_segment.get("data")
                        if msg_type_segment == "image":
                            url = msg_data_segment.get("url") or msg_data_segment.get("file_url")
                            file_id = msg_data_segment.get("file") or msg_data_segment.get("file_id")
                            local_path = await download_file(url, msg_type_segment, file_id)  # type: ignore
                            file_data = await to_gemini_init_data(local_path)
                            file_list.append(file_data)
                        elif msg_type_segment == "file":
                            file_id = msg_data_segment.get("file_id")
                            file_url_info = await bot.call_api(
                                "get_group_file_url",
                                file_id=file_id,
                                group_id=event.group_id,  # type: ignore
                            )
                            url = file_url_info["url"]
                            local_path = await download_file(url, msg_type_segment, file_id)
                            file_data = await to_gemini_init_data(local_path)
                            file_list.append(file_data)
                        elif msg_type_segment == "text":
                            text_data += f"{msg_data_segment.get('text').strip()}，"
            else:
                text_data = reply.message.extract_plain_text()
    else:
        for segment in event.message:
            # 处理消息中携带图片
            if segment.type == "image":
                img_data = segment.data
                file_id = img_data.get("file") or img_data.get("file_id")
                url = img_data.get("url") or img_data.get("file_url")
                local_path = await download_file(url, segment.type, file_id)  # type: ignore
                file_data = await to_gemini_init_data(local_path)
                file_list.append(file_data)
    return file_list, text_data


async def fetch_gemini_req(query: str, file_list: List[Dict] = []) -> str:
    old_http_proxy = os.environ.get("HTTP_PROXY")
    old_https_proxy = os.environ.get("HTTPS_PROXY")
    if (old_http_proxy is None or old_https_proxy is None) and plugin_config.gm_proxy:
        os.environ["HTTP_PROXY"] = plugin_config.gm_proxy
        os.environ["HTTPS_PROXY"] = plugin_config.gm_proxy
    content_list = [PROMPT, query] if file_list == [] else [PROMPT, query, *file_list]
    response = await model.generate_content_async(content_list)
    if old_http_proxy is None and old_https_proxy is None:
        if "HTTP_PROXY" in os.environ:
            del os.environ["HTTP_PROXY"]
        if "HTTPS_PROXY" in os.environ:
            del os.environ["HTTPS_PROXY"]
    return response.text


async def gemini_search_extend(query: str) -> str:
    query = quote(query.replace("搜索", ""))
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    logger.debug(url)
    payload = {"contents": [{"parts": [{"text": PROMPT}, {"text": query}]}], "tools": [{"googleSearch": {}}]}
    headers = {"Content-Type": "application/json"}
    async with httpx.AsyncClient(
        proxies=plugin_config.gm_proxy if plugin_config.gm_proxy else None, timeout=300
    ) as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            response = "".join(
                item.get("text", "") for item in data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            )
            search_source = data.get("candidates", [{}])[0].get("groundingMetadata", {}).get("groundingChunks", [])
            if search_source:
                search_sources = []
                for source in search_source:
                    search_sources.append(
                        f"📌 网站：{source.get('web', {}).get('title', '')}\n"
                        f"🌍 来源：{source.get('web', {}).get('uri', '')}"
                    )
                response += "\n" + "\n".join(search_sources)
        else:
            response = "抱歉，Gemini搜索功能暂时无法使用，请切换为LLMCrawl搜索。"
    return response


async def to_gemini_init_data(file_path):
    # 获取文件的 MIME 类型
    mime_type = mimetypes.guess_type(file_path)[0]
    async with aiofiles.open(file_path, "rb") as f:
        # 读取文件内容
        data = await f.read()
        # 返回正确格式的字典
        return {"mime_type": mime_type, "data": base64.b64encode(data).decode("utf-8")}


async def download_file(url: str, file_type: str, file_id: str) -> str:
    try:
        # 创建保存文件的目录
        local_dir = store.get_plugin_data_file("tmp")
        local_dir.mkdir(parents=True, exist_ok=True)

        # 提取文件名
        if "." in file_id:
            base_name, ext_file_id = file_id.rsplit(".", 1)  # 分离文件名和后缀
            simplified_file_id = base_name[:8]  # 截取文件名的前 8 位

        # 使用 httpx 异步下载文件
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()  # 检查 HTTP 状态码

            # 安全文件名处理
            ext = f".{ext_file_id}"  # type: ignore
            name = "".join(c if c.isalnum() or c in "-_." else "_" for c in Path(simplified_file_id).stem)  # type: ignore
            safe_filename = f"{file_type}_{name}{ext}"

            # 生成文件保存路径
            local_path = local_dir / safe_filename

            # 异步写入文件
            async with aiofiles.open(local_path, "wb") as f:
                await f.write(response.content)

        logger.debug(f"文件已成功下载到: {local_path}")
        return str(local_path)

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP 错误：{e.response.status_code} - {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"下载文件时出错：{e}")
        raise


@scheduler.scheduled_job("cron", hour=8, id="job_gemini_clean_tmps")
async def clean_gemini_tmps():
    """
    每日清理 Gemini 临时文件
    :return: None
    """
    local_dir = store.get_plugin_data_file("tmp")
    await remove_all_files_in_dir(local_dir)
