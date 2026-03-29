"""DateTime tool - returns current date and time."""

from datetime import datetime, timezone

from backend.agents.tools.base import BaseTool, ToolContext, ToolResult


class DateTimeTool(BaseTool):
    name = "get_current_datetime"
    description = "Get the current date and time in the specified timezone."
    parameters = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Timezone name, e.g. 'Asia/Shanghai', 'US/Eastern'. Defaults to UTC.",
                "default": "UTC",
            }
        },
        "required": [],
    }

    async def execute(self, params: dict, context: ToolContext) -> ToolResult:
        tz_name = params.get("timezone", "UTC")
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            tz = timezone.utc
            tz_name = "UTC"

        now = datetime.now(tz)
        return ToolResult(
            success=True,
            output=f"Current time in {tz_name}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            data={"datetime": now.isoformat(), "timezone": tz_name},
        )
