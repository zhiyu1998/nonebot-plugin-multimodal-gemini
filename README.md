<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://s2.loli.net/2024/12/05/97BPodAZpy4GEuh.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonbot-plugin-multimodal-gemini

_✨Nonebot2 的谷歌 Gemini 多模态助手，一个命令即可玩转 Gemini 的多模态！✨_

<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/owner/nonebot-plugin-auto-sendlike.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-auto-sendlike">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-auto-sendlike.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">

</div>

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonbot-plugin-multimodal-gemini

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonbot-plugin-multimodal-gemini
</details>
<details>
<summary>pdm</summary>

    pdm add nonbot-plugin-multimodal-gemini
</details>
<details>
<summary>poetry</summary>

    poetry add nonbot-plugin-multimodal-gemini
</details>
<details>
<summary>conda</summary>

    conda install nonbot-plugin-multimodal-gemini
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonbot-plugin-multimodal-gemini"]

</details>

## ⚙️ 配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| gm_api_key | 是 | 无 | 配置说明 |
| gm_model | 否 | gemini-1.5-flash | 配置说明 |
| gm_prompt | 否 | 请用中文回答以下问题： | 配置说明 |

## 🎉 使用

### 指令表
|       指令        | 权限 | 需要@ |  范围   | 说明 |
|:---------------:|:----:|:----:|:-----:|:----:|
| gemini / Gemini | 群员 | 否 | 群聊/私聊 | 指令说明 |

### 效果图

![](https://s2.loli.net/2024/12/05/2toGhBxZLzeHk9V.png)