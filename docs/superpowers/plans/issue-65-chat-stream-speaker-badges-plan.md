# Implementation Plan: [octop-adoption] 实现 ChatStreamView 多专家真群聊流式上墙与身份标记 (Issue #65)

## Overview
落实 TencentCloud/Octop 真群聊协同视觉体验，在 ATBMind 运行时事件总线中增加 `SpeakerStreamEvent`，并在桌面端 `MessageBubble` 和 `ChatStreamView` 中实现专家身份徽章与多专家交替流式输出上墙。

---

## Tasks

### Task 1: 编写单元测试 `tests/test_stream_speaker.py`
- 编写覆盖 `SpeakerStreamEvent` 的发布与订阅测试；
- 编写覆盖 `EventBusQtBridge` 信号中转测试；
- 编写覆盖 `AssistantTextMessageItem` 带有专家身份（徽章、名称、头像）及 `append_text` 流式追加的渲染测试；
- 编写覆盖 `ChatStreamView.append_speaker_delta` 多专家交替流式输出自动开辟新气泡的测试。
- **Command**: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_stream_speaker.py -v` (Confirm initial failure before implementation).

### Task 2: 扩展 `atbmind_core/runtime/event_bus.py` 与 `apps/atbmind_desktop/bridge.py`
- 在 `atbmind_core/runtime/event_bus.py` 中新增 `SpeakerStreamEvent` 类；
- 在 `apps/atbmind_desktop/bridge.py` 中增加 `speaker_stream_received` 信号及订阅处理逻辑。

### Task 3: 改造 `apps/atbmind_desktop/widgets/message_bubble.py`
- 为 `AssistantTextMessageItem` 扩展 `speaker_role_id`、`speaker_name`、`speaker_avatar` 等参数；
- 实现动态专家徽章与个性化图标展示；
- 提供 `append_text(delta: str)` 及 `set_content(content: str)` 方法用于实时追加流式 token。

### Task 4: 改造 `apps/atbmind_desktop/widgets/chat_stream.py`
- 支持追踪 `_current_speaker_bubble` 与 `_current_speaker_id`；
- 实现 `append_speaker_delta(...)`，根据专家 ID 自动判断是否复用当前气泡或新建下一个专家的气泡；
- 在 `add_assistant_message` 中支持传入专家身份参数；
- 确保滚动条自动跟随滚到底部。

### Task 5: 验证测试套件无回归
- 运行 `tests/test_stream_speaker.py`；
- 运行 `tests/test_chat_stream.py`；
- 运行全量测试套件并保证 100% 通过。

### Task 6: grill-me 质量审计并准备代码评审
- 检查代码风格、异常边界、内存与信号管理；
- 推进状态机至 `reviewing` 并自动交由 `atb-github-code-reviewer`。
