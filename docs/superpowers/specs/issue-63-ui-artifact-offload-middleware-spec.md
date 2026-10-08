# Specification: Issue #63 - UI Artifact 旁路中间件与大 Payload 剥离解耦

**Issue**: [#63 [octop-adoption] 实现 UI Artifact 旁路中间件与大 Payload 剥离解耦](https://github.com/aitobox/ATBMind/issues/63)  
**Parent Epic**: #62 (Octop-inspired Architecture Evolution)  
**Branch**: `agent/issue-63-ui-artifact-offload-middleware`  
**Status**: In Progress  

---

## 1. 目标与背景

在 ATBMind 现有实现中，工具执行返回的绘图参数、长文本或复杂卡片结构体直接填充在 `ToolMessage.content` 中。在随后的多轮对话中，这部分巨型 Payload 会被反复发送至 LLM，导致上下文 Token 消耗急剧膨胀，干扰模型推理注意力。

借鉴 TencentCloud/Octop 的 `OctopUiOffloadMiddleware` 架构哲学，建立数据面与控制面的彻底解耦：
1. **控制面（LLM Context）**：仅保留极简的纯文本摘要和数据引用标识（`{"data_ref": "artifact", "summary": "..."}`），保证极高性价比与注意力集中；
2. **数据面（UI & Storage）**：完整结构体大 Payload 剥离至 `ToolResult.artifact`，在事件总线 `TOOL_CALL_END` 及 `AgentMessage.metadata` 中透传并持久化，供桌面端（PySide6）富组件直接解码渲染。

---

## 2. 详细接口设计与契约

### 2.1 `ToolResult` 扩展 (`atbmind_core/harness/tools/base.py` & `atbmind_core/harness/types.py`)
```python
@dataclass
class ToolResult:
    content: str
    is_error: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    terminate: bool = False
    artifact: Optional[Dict[str, Any]] = None  # 新增: 专门承载前端大 Payload / 富卡片数据
```
在 `atbmind_core/harness/types.py` 中导出 `ToolResult`，确保从 `types` 或 `tools.base` 导入均一致。

### 2.2 大模型请求转换器 `to_model_message` (`atbmind_core/harness/types.py`)
```python
def to_model_message(message: AgentMessage | ToolResult | Dict[str, Any]) -> Dict[str, Any]:
    """
    将 AgentMessage 或 ToolResult 转化为符合大模型推理要求的标准字典格式。
    严格剔除任何 artifact 或多余内部 metadata，仅保留 role, content, name, tool_call_id 等控制面信息。
    """
```
同时升级 `AgentMessage.to_llm_dict()`，确保无论输入何种包含 `artifact` 的元数据，进入 LLM 的字典均无 `artifact`。

### 2.3 `ArtifactOffloadMiddleware` (`atbmind_core/harness/middleware/artifact_offload.py`)
#### 剥离规则条件：
1. `ToolResult` 执行成功（`is_error == False`）；
2. 内容长度 $\ge 3000$ 字符（可配置 `threshold: int = 3000`）；
3. 内容是合法 JSON 字符串或字典，且包含 `atbmind_ui` 声明（或根节点包含 `"atbmind_ui": True` 或嵌套声明）；
4. 剥离执行：
   - 将完整解析出的数据结构移存至 `ToolResult.artifact`；
   - 原 `content` 替换为紧凑摘要 JSON：
     ```json
     {
       "data_ref": "artifact",
       "type": "<atbmind_ui_type>",
       "summary": "<自动生成的轻量摘要，限150字内>"
     }
     ```
   - 在 `ToolResult.metadata` 中标记 `offloaded: True`；
5. 容错性与平滑降级：非合法 JSON、异常解析或未命中条件的内容原样透传，严禁阻断流程。

### 2.4 `agent_loop` 挂载与事件透传 (`atbmind_core/harness/loop.py`)
1. 在 `AgentLoopConfig` 中支持 `middlewares: Optional[List[Any]] = None`，并默认挂载 `ArtifactOffloadMiddleware()`；
2. `TOOL_CALL_END` 事件负载中包含 `artifact: res.artifact`；
3. 构建 `AgentMessage(role=Role.TOOL)` 时，若 `res.artifact` 存在，挂载至 `tool_msg.metadata["artifact"] = res.artifact`。

---

## 3. Implementation Task List

- [ ] Task 1: Module design & contract definitions (`ToolResult.artifact`, `to_model_message` in `atbmind_core/harness/types.py` & `base.py`)
- [ ] Task 2: Unit tests & TDD test cases (`tests/test_artifact_offload.py`)
- [ ] Task 3: `ArtifactOffloadMiddleware` implementation & `agent_loop` middleware chain integration
- [ ] Task 4: Integration verification & full test suite pass (zero regressions across 338+ tests)
- [ ] Task 5: grill-me audit & stress-testing
