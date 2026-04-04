"""Weather query tool using wttr.in API."""

import logging
import httpx
from backend.agents.tools.base import BaseTool, ToolContext, ToolResult

logger = logging.getLogger(__name__)


class WeatherTool(BaseTool):
    name = "get_weather"
    description = "查询指定城市的当前天气信息，包括温度、天气状况等"
    parameters = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市名称，如：北京、上海、Tokyo、New York"
            }
        },
        "required": ["city"]
    }

    async def execute(self, params: dict, context: ToolContext) -> ToolResult:
        city = params.get("city", "")
        if not city:
            return ToolResult(success=False, output="请提供城市名称")

        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(
                    f"https://wttr.in/{city}",
                    params={"format": "j1"},
                    headers={"Accept-Language": context.language or "zh"},
                )
                if resp.status_code != 200:
                    return ToolResult(success=False, output=f"查询失败: HTTP {resp.status_code}")

                data = resp.json()
                current = data.get("current_condition", [{}])[0]

                temp_c = current.get("temp_C", "?")
                feels_like = current.get("FeelsLikeC", "?")
                humidity = current.get("humidity", "?")
                desc_cn = current.get("lang_zh", [{}])
                desc = desc_cn[0].get("value", "") if desc_cn else current.get("weatherDesc", [{}])[0].get("value", "")
                wind_speed = current.get("windspeedKmph", "?")

                output = f"{city}当前天气：{desc}，温度{temp_c}°C（体感{feels_like}°C），湿度{humidity}%，风速{wind_speed}km/h"

                return ToolResult(
                    success=True,
                    output=output,
                    data={
                        "city": city,
                        "temp_c": temp_c,
                        "feels_like_c": feels_like,
                        "humidity": humidity,
                        "description": desc,
                        "wind_speed_kmph": wind_speed,
                    }
                )
        except httpx.TimeoutException:
            return ToolResult(success=False, output=f"查询{city}天气超时，请稍后再试")
        except Exception as e:
            logger.error(f"Weather query failed: {e}")
            return ToolResult(success=False, output=f"天气查询失败: {str(e)[:50]}")
