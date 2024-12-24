from pydantic import BaseModel, Extra


class Config(BaseModel, extra=Extra.ignore):
    # Gemini 配置
    gm_api_key: str = ""  # Gemini API 密钥列表
    gm_model: str = "gemini-2.0-flash-exp"  # 默认模型名称
    gm_prompt: str = "请用中文回答以下问题："  # 通用提示词
    gm_proxy: str = ""  # 代理设置
    gm_search: bool = True  # 是否启用 GeminiSearch
