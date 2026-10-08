# Spec: [octop-adoption] 实现 ChatStreamView 多专家真群聊流式上墙与身份标记 (Issue #65)

## 1. 目标与背景 (Objective & Context)
借鉴 TencentCloud/Octop 的「真群聊上墙」协同呈现机制：在多智能体（Coordinator 与多个专家角色）执行时，专家执行的实时流式 token、消息气泡和工具卡片需要携带 `speaker_role_id`、`speaker_name`、`speaker_avatar` 等身份信息。在桌面端 `ChatStreamView` 主时间线上交替呈现不同的专家气泡与身份徽章（Speaker Badge），为用户营造团队并肩作战的直观协作视觉体验。

## 2. 核心架构设计 (Architecture Design)

### 2.1 数据层与运行时事件扩展
1. **`SpeakerStreamEvent` (atbmind_core/runtime/event_bus.py)**:
   - 继承 `RuntimeEvent`，用于流式多专家 token 实时推送；
   - 字段包括：`speaker_role_id: str`、`speaker_name: str`、`speaker_avatar: str`、`delta: str`、`is_start: bool = False`、`is_end: bool = False`、`message_id: str = ""`。
2. **`EventBusQtBridge` (apps/atbmind_desktop/bridge.py)**:
   - 订阅 `SpeakerStreamEvent`，发射 `speaker_stream_received = Signal(dict)` Qt 信号，确保跨线程安全同步至 Qt 主线程。

### 2.2 UI 表现层升级
1. **`AssistantTextMessageItem` (apps/atbmind_desktop/widgets/message_bubble.py)**:
   - 构造参数支持 `speaker_role_id: Optional[str] = None`、`speaker_name: Optional[str] = None`、`speaker_avatar: Optional[str] = None`；
   - 顶部徽章（Badge）动态展示专家专属标识：例如 `✦ [团队协调官]`、`🎨 [AI画画专家]`、`💻 [代码工程师]`；
   - 支持动态设置/追加文本（`append_text(delta: str)`），便于流式实时更新内容；
   - 支持设置或高亮特定专家的专属徽章主题色彩。
2. **`ChatStreamView` 动态气泡路由与平滑上墙 (apps/atbmind_desktop/widgets/chat_stream.py)**:
   - 维护当前活跃的流式气泡追踪：`_current_stream_bubble: Optional[AssistantTextMessageItem]` 及 `_current_speaker_id: Optional[str]`；
   - 提供 `append_speaker_delta(speaker_role_id: str, speaker_name: str, delta: str, speaker_avatar: str = "", is_start: bool = False, is_end: bool = False)` 方法：
     - 若 `speaker_role_id` 与当前活跃气泡的专家不一致，或者当前无活跃气泡，则平滑结束前一个气泡并新建该专家的专属气泡插入流中；
     - 自动滚屏至最新内容；
     - 当收到 `is_end=True` 时收口当前气泡。
   - `add_assistant_message` 方法增强，兼容传入专家身份元数据。

## 3. 验收标准与任务清单 (Acceptance Criteria & Task Checklist)

- [ ] Task 1: 编写单元测试 `tests/test_stream_speaker.py` 覆盖 EventBus 专家元数据透传、Speaker Badge 渲染与 ChatStreamView 动态气泡路由
- [ ] Task 2: 扩展 `atbmind_core/runtime/event_bus.py`，新增 `SpeakerStreamEvent`，并更新 `EventBusQtBridge`
- [ ] Task 3: 改造 `apps/atbmind_desktop/widgets/message_bubble.py`，支持 Speaker Badge 徽章与专家头像及流式追加
- [ ] Task 4: 改造 `apps/atbmind_desktop/widgets/chat_stream.py`，实现多专家交替流式输出与独立气泡创建/追加
- [ ] Task 5: 运行 `tests/test_stream_speaker.py` 及全量测试套件验证无回归
- [ ] Task 6: 实施 grill-me 质量审计并准备代码评审
