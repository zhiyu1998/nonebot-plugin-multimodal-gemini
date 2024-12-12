import base64
import mimetypes
from pathlib import Path
from typing import List

import aiohttp

from .utils import remove_all_files_in_dir, contains_http_link

import aiofiles
import google.generativeai as genai
import httpx

from nonebot import on_command, get_plugin_config, require
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, GroupMessageEvent
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot.plugin import PluginMetadata
from nonebot.rule import is_type

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
        "(2) llama搜索：gemini搜索 + [问题]（测试功能尚未生效）\n\n"
        "支持引用的文件格式有：\n"
        "  音频: .wav, .mp3, .aiff, .aac, .ogg, .flac\n"
        "  图片: .png, .jpeg, .jpg, .webp, .heic, .heif\n"
        "  视频: .mp4, .mpeg, .mov, .avi, .flv, .mpg, .webm, .wmv, .3gpp\n"
        "  文档: .pdf, .js, .py, .txt, .html, .htm, .css, .md, .csv, .xml, .rtf"
    ),
    type="application",
    homepage="https://github.com/zhiyu1998/nonebot-plugin-multimodal-gemini",
    config=Config,
    supported_adapters={ "~onebot.v11" }
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
gemini = on_command("gemini", aliases=set("Gemini"), priority=5, rule=is_type(GroupMessageEvent), block=True)


# 处理多模态内容或文本问题
@gemini.handle()
async def chat(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    query = args.extract_plain_text().strip()
    url, msg_type, file_id = await auto_get_url(bot, event)
    logger.info(f"链接{url}，类型{msg_type}，文件ID{file_id}")
    if url != '' and msg_type != 'text':
        # 下载文件到本地
        local_path = await download_file(url, msg_type, file_id)
        completion: str = await fetch_gemini_req(query, local_path)
        await gemini.finish(Message(completion), reply_message=True)
    # 如果只是文字
    if msg_type == "text":
        query += f"引用：{url}"

    if query.startswith("搜索") or contains_http_link(query):
        search_ans = await gemini_search_extend(query)
        await gemini.finish(search_ans, reply_message=True)

    completion: str = await fetch_gemini_req(query)
    await gemini.finish(Message(completion), reply_message=True)


async def gemini_search_extend(query: str) -> str | None:
    """
        Gemini 的搜索扩展
    :param query:
    :return:
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    logger.debug(url)

    payload = {
        "contents": [
            {
                "parts": [
                    { "text": PROMPT },
                    { "text": query }
                ]
            }
        ],
        "tools": [
            {
                "googleSearch": { }
            }
        ]
    }

    headers = {
        "Content-Type": "application/json"
    }

    timeout = aiohttp.ClientTimeout(total=100)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                ans = data.get("candidates", [{ }])[0].get("content", { }).get("parts", [{ }])[0].get("text")
            else:
                ans = None

    return ans


async def auto_get_url(bot: Bot, event: MessageEvent):
    # 判断是否存在回复
    reply = event.reply
    if reply:
        # logger.info(reply)
        url = ''
        for segment in reply.message:
            msg_type = segment.type  # 消息类型
            msg_data = segment.data  # 消息内容
            # 根据消息类型处理
            if msg_type in ["image", "audio", "video"]:
                url = msg_data.get("url") or msg_data.get("file_url")  # 提取视频或图片的 URL
                file_id = msg_data.get("file") or msg_data.get("file_id")
                # 调用 handle_file_or_image 处理引用内容
                return url, msg_type, file_id
            elif msg_type == "file":
                file_id = msg_data.get("file_id")
                file_url_info = await bot.call_api("get_group_file_url", file_id=file_id,
                                                   group_id=event.group_id)  # 提取文件的 URL
                url = file_url_info["url"]
                # 调用 handle_file_or_image 处理引用内容
                return url, msg_type, file_id
        if url == '':
            url = reply.message.extract_plain_text()
            return url, 'text', ''
    else:
        return "", "", None


async def fetch_gemini_req(query: str | List[str], file_path='') -> str:
    content_list = [PROMPT, query] if file_path == '' else [PROMPT, query, to_gemini_init_data(file_path)]

    response = await model.generate_content_async(content_list)
    return response.text


def to_gemini_init_data(file_path):
    # 获取文件的 MIME 类型
    mime_type = mimetypes.guess_type(file_path)[0]
    with open(file_path, 'rb') as f:
        # 读取文件内容
        data = f.read()
        # 返回正确格式的字典
        return {
            'mime_type': mime_type,
            'data': base64.b64encode(data).decode('utf-8')
        }


async def download_file(url: str, file_type: str, file_id: str) -> str:
    try:
        # 创建保存文件的目录
        local_dir = store.get_plugin_data_file("tmp")
        local_dir.mkdir(parents=True, exist_ok=True)

        # 提取文件名
        if '.' in file_id:
            base_name, ext_file_id = file_id.rsplit('.', 1)  # 分离文件名和后缀
            simplified_file_id = base_name[:8]  # 截取文件名的前 8 位

        # 使用 httpx 异步下载文件
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()  # 检查 HTTP 状态码

            # 安全文件名处理
            ext = f".{ext_file_id}"
            name = "".join(c if c.isalnum() or c in "-_." else "_" for c in Path(simplified_file_id).stem)
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


@scheduler.scheduled_job('cron', hour=8, id="job_gemini_clean_tmps")
async def clean_gemini_tmps():
    """
    每日清理 Gemini 临时文件
    :return: None
    """
    local_dir = store.get_plugin_data_file("tmp")
    await remove_all_files_in_dir(local_dir)
