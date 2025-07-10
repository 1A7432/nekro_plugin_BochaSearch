import httpx
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.core import logger
from nekro_agent.services.plugin.base import ConfigBase, NekroPlugin, SandboxMethodType
from pydantic import Field

logger.info("正在加载博查 AI 搜索插件 (nekro_plugin_bocha_search)...")

# 插件元信息
plugin = NekroPlugin(
    name="博查 AI 搜索",
    module_name="nekro_plugin_bocha_search",
    description="通过博查 Web Search API 进行联网搜索",
    version="2.0.0",
    author="dirac",
    url="https://github.com/1A7432/nekro_plugin_BochaSearch",
)


# 插件配置
@plugin.mount_config()
class BochaConfig(ConfigBase):
    """博查搜索插件配置"""

    API_URL: str = Field(
        default="https://api.bochaai.com/v1",
        title="博查 API 地址",
        description="通常不需要修改。",
    )
    API_KEY: str = Field(
        default="",
        title="博查 API Key",
        description="您的博查 API 密钥，以 'sk-' 开头。",
    )
    SEARCH_RESULT_COUNT: int = Field(
        default=5,
        title="搜索结果数量",
        description="返回的搜索结果数量，范围 1-10。",
        ge=1,
        le=10,
    )


# 获取配置实例
config: BochaConfig = plugin.get_config(BochaConfig)


@plugin.mount_sandbox_method(SandboxMethodType.AGENT, name="搜索", description="使用博查AI进行联网搜索并返回结果")
async def search_ai(_ctx: AgentCtx, query: str) -> str:
    """根据用户提供的关键词进行联网搜索，并返回格式化后的结果。

    Args:
        query: 需要搜索的关键词。

    Returns:
        str: 格式化后的搜索结果，包含标题、链接和摘要。

    Example:
        search_ai(query="天空为什么是蓝色的？")
    """
    if not config.API_KEY:
        error_msg = "插件配置不完整，请前往插件设置填写 API_KEY。"
        logger.error(error_msg)
        return error_msg

    api_url = f"{config.API_URL.rstrip('/')}/web-search"
    headers = {
        'Authorization': f'Bearer {config.API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        "query": query,
        "summary": True,  # 强制获取摘要
        "count": config.SEARCH_RESULT_COUNT
    }

    logger.info(f"开始使用博查进行搜索: {query}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()  # 如果状态码是 4xx 或 5xx，则抛出异常

        response_data = response.json()

        if response_data.get("code") != 200:
            error_msg = f"博查 API 返回错误: {response_data.get('msg', '未知错误')}"
            logger.error(error_msg)
            return error_msg

        web_pages = response_data.get("data", {}).get("webPages", {}).get("value", [])

        if not web_pages:
            return f"未能找到与“{query}”相关的结果。"

        # 格式化输出
        result_parts = [f"为您找到关于“{query}”的相关信息如下:\n"]
        for i, page in enumerate(web_pages, 1):
            title = page.get('name', '无标题')
            url = page.get('url', '无链接')
            snippet = page.get('summary') or page.get('snippet', '无摘要')
            result_parts.append(f"{i}. {title}\n   链接: {url}\n   摘要: {snippet.strip()}\n")

        final_result = "\n".join(result_parts)
        logger.info(f"博查搜索成功，返回 {len(web_pages)} 条结果。")
        return final_result

    except httpx.HTTPStatusError as e:
        error_body = e.response.text
        logger.error(f"调用博查 API 时发生 HTTP 错误: {e.response.status_code}, 响应: {error_body}")
        return f"搜索服务请求失败，状态码: {e.response.status_code}。请检查您的网络或 API Key。"
    except Exception as e:
        logger.error(f"调用博查 API 时发生未知错误: {e}")
        return f"搜索时遇到未知错误: {e}"
