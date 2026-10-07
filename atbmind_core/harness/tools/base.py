"""
ATBMind AgentTool Base Definition and Schemas
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

class ExecutionMode(StrEnum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"

@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    terminate: bool = False

    @property
    def success(self) -> bool:
        return not self.is_error

    @property
    def output(self) -> str:
        return self.content

    @property
    def error(self) -> str:
        return self.content if self.is_error else ""

    def __await__(self):
        async def _identity():
            return self
        return _identity().__await__()


class AgentTool:
    """
    Abstract base class for all Agent tools.
    Supports automatic OpenAI function schema generation via Pydantic.
    """

    name: str = ""
    description: str = ""
    parameters_schema: Type[BaseModel]
    execution_mode: ExecutionMode = ExecutionMode.PARALLEL

    async def execute(self, args: Dict[str, Any], context: Optional[Any] = None) -> ToolResult:
        """Executes the tool with validated arguments."""
        raise NotImplementedError

    def to_openai_schema(self) -> Dict[str, Any]:
        """Generates the standard OpenAI function calling tool definition."""
        schema = self.parameters_schema.model_json_schema()
        # Clean title and extra metadata if needed
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }
