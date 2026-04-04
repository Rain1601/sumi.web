"""Web search tool using DuckDuckGo API."""

import logging
import httpx
from backend.agents.tools.base import BaseTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "搜索互联网获取最新信息、新闻、知识等"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词"
            }
        },
        "required": ["query"]
    }

    async def execute(self, params: dict, context: ToolContext) -> ToolResult:
        query = params.get("query", "")
        if not query:
            return ToolResult(success=False, output="请提供搜索关键词")

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                # DuckDuckGo Instant Answer API (free, no API key)
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": "1",
                        "skip_disambig": "1",
                    },
                )
                data = resp.json()

                # Try to get abstract/answer
                abstract = data.get("AbstractText", "")
                answer = data.get("Answer", "")
                heading = data.get("Heading", "")

                # Try related topics if no abstract
                results = []
                if abstract:
                    results.append(abstract)
                elif answer:
                    results.append(answer)

                # Add top related topics
                for topic in data.get("RelatedTopics", [])[:3]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append(topic["Text"])

                if not results:
                    # Fallback: try a simple search summary
                    return ToolResult(
                        success=True,
                        output=f"搜索 \"{query}\" 暂无直接结果，建议用户自行搜索获取最新信息。",
                        data={"query": query, "source": "duckduckgo"}
                    )

                output = f"搜索结果 \"{query}\":\n" + "\n".join(results[:3])

                return ToolResult(
                    success=True,
                    output=output[:500],  # Limit length for voice
                    data={
                        "query": query,
                        "heading": heading,
                        "results_count": len(results),
                        "source": "duckduckgo",
                    }
                )
        except httpx.TimeoutException:
            return ToolResult(success=False, output="搜索超时，请稍后再试")
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return ToolResult(success=False, output=f"搜索失败: {str(e)[:50]}")
