# ATBMind 桌面端 UI 重构与多轮插件化平台架构设计规范

- **状态**: Approved by Grill Review
- **日期**: 2026-09-29
- **最后修订**: 2026-09-29 (经过 11 轮 Grill-Me 压力审查与边界确认)
- **作者**: ATBMind Core Team
- **目标路径**: `docs/superpowers/specs/2026-09-29-atbmind-ui-redesign-design.md`

---

## 1. 背景与目标 (Context & Objectives)

### 1.1 背景
当前项目处于将专用绘图工具演进为通用 AI 智能体平台的关键阶段。此前，`apps/atb_draw_desktop` 实现了针对人像精修的独立原型客户端，采用固定卡片与右侧抽屉参数调节，缺乏多轮连续交互能力和多会话管理机制。

为了确立 **ATBMind** 作为核心应用框架的平台化定位（ATBDraw 仅作为其首个核心能力插件），需要对整个 UI 架构与数据流进行彻底重塑。新界面参考业界领先的 AI 对话范式（如豆包等现代客户端），打造优雅、高效的 macOS 原生质感桌面应用。

### 1.2 核心目标
1. **统一平台入口**：在 `apps/atbmind_desktop` 构建全新的旗舰级桌面主程序，使 ATBMind 成为多会话、多插件管理中心。
2. **多轮对话与流式渲染**：支持连续多轮人机交互，不仅支持通用 LLM 文本交流，更能在对话流中无缝渲染 ATBDraw 的多轮生图与精修对比结果卡片。
3. **可插拔底部控制台 (Pluggable Footer Dock)**：输入区域支持动态挂载插件。挂载 ATBDraw 时，自动呈现模型选择、长宽比、艺术风格浮层菜单 (Popover) 与修图模板下拉框。
4. **灵活多模态附件流**：输入框内置附件支持，用户可通过文件选取或拖拽上传人像原图，在输入栏生成微型缩略图卡片（Thumbnail Chip），支持随提示词一同提交；在未提供图片时允许自然纯文本交互。
5. **完整本地持久化**：会话元数据、历史聊天流与生成的图片路径全部持久化到 SQLite 数据库 (`data/atbmind.db`)；LLM API 配置持久化至 `configs/config.yaml`；生成图片保存在本地专用目录 `data/generated_images/`。
6. **异步流畅体验**：所有推理、图像生成与标题自动提炼逻辑移至后台 `QThread` 异步执行，界面状态实时响应，坚决避免主线程卡顿。

---

## 2. 总体架构与系统分层 (Architecture & Layering)

系统采用 **宿主-插件解耦 (Host-Plugin Decoupling)** 与 **事件驱动状态机 (Event-Driven State Machine)** 模式，整体划分为四层：

```
+-----------------------------------------------------------------------------------+
|                              Presentation Layer (PySide6)                         |
|  [SidebarWidget]         [ChatStreamView]                  [FooterDock]           |
|  - + 新对话 (⌘N)          - UserBubble (+Attachment Chip)   - PluginControlBar     |
|  - 历史会话列表            - AssistantBubble                 - StylePopover 网格    |
|  - ⚙️ 设置 (Settings)     - DrawResultCard (Before/After)   - PromptInput (+Chip)  |
|                          - ErrorCard (内联重试卡片)                                |
+-----------------------------------------+-----------------------------------------+
                                          | Signals / State Actions
+-----------------------------------------v-----------------------------------------+
|                               State & Coordinator Layer                           |
|  [UIStateManager]                [SessionController]       [GenerationWorker]     |
|  - 管理当前 Session 指针           - 驱动消息增删改查         - QThread 异步生图/推理|
|  - 插件 UI 挂载/状态恢复          - 异步 LLM 标题生成        - TitleWorker 异步摘要 |
+-----------------------------------------+-----------------------------------------+
                                          | Data Access & Invocations
+-----------------------------------------v-----------------------------------------+
|                                Core Engine & Plugins                              |
|  [ATBMind Core Engines]         [Plugin System]            [ATBDraw Plugin]       |
|  - Completer / Planner          - PluginRegistry           - DrawVisionExtractor  |
|  - Dispatcher / LLMClient       - PluginUISpec 声明契约    - ImageModelAdapters   |
|  (负责 Context Window 截断)                                                        |
+-----------------------------------------+-----------------------------------------+
                                          | Persistence
+-----------------------------------------v-----------------------------------------+
|                                  Storage Layer                                    |
|  [SessionStore (SQLite)]        [Local Image Store]        [ConfigManager (YAML)] |
|  - tables: sessions, messages   - data/generated_images/   - configs/config.yaml  |
+-----------------------------------------------------------------------------------+
```

---

## 3. UI 布局与详细组件规范 (UI Layout & Component Specifications)

主界面尺寸默认为 `1200 x 780`，最低适配 `1024 x 640`。设计明确采用 **Apple HIG 纯浅色系风格**（无深色模式分支，聚焦高品质 Light UI）：
* 主背景：`#ffffff`
* 侧边栏背景：`#f7f7f8`
* 分界线：`#e5e5ea`
* 主题蓝：`#0071e3`（Hover: `#0077ed`）
* 辅助文本：`#86868b`

### 3.1 左侧侧边栏 (`SidebarWidget`)
* **宽度**：固定 `250px`，背景色 `#f7f7f8`，右边缘浅灰分界线 `#e5e5ea`。
* **顶部 Branding 与新建入口**：
  * 应用 Logo 与标题 `ATBMind`（16px 粗体）。
  * **`+ 新对话` 按钮**：高亮悬浮按钮，支持快捷键 `Cmd+N`。
  * **新建行为**：新建会话默认**不挂载任何插件**（即 `active_plugin_id = None`，纯文本对话模式），右侧清空并展示通用对话态。
* **中部会话历史列表 (`SessionListView`)**：
  * 卡片列表展示历史会话，按 `updated_at` 倒序排列。
  * 每项展示：会话标题、更新时间、插件小徽章（如绘图会话带有 🎨 小图标）。
  * **切会话行为**：点击切回历史会话时，完整读取该会话的 `plugin_state`，并在 FooterDock 中恢复其选择的模型、比例、风格与模板参数。
  * 悬浮态与右键菜单：支持「重命名」和「删除会话」。
* **底部设置栏**：
  * 包含当前环境与版本信息，以及 `⚙️ 设置` 按钮。
  * 点击弹出全局模态对话框 `SettingsDialog`。

### 3.2 中央多轮对话流 (`ChatStreamView`)
* **顶部信息条 (`ChatHeaderBar`)**：
  * 展示当前会话标题（支持双击就地重命名编辑）。
  * 挂载插件指示器：未挂载插件时显示 `[💬 通用对话]`；载入 ATBDraw 后显示 `[🎨 ATBDraw: 图像生成]` 徽章。
  * 右侧操作：清空当前会话历史、删除会话快捷按钮。
* **滚动容器 (`QScrollArea`)**：
  * 垂直流式布局，底部加 stretch，收到新消息时平滑滚动至最下方。全量渲染历史气泡，超出可视范围随窗口往上平滑滚动。
* **消息组件渲染**：
  1. **用户消息气泡 (`UserMessageItem`)**：
     * 右对齐或左侧高亮气泡。
     * 若包含附件图片，在文字上方展示带圆角的原图缩略预览（可点击全屏放大）。
     * 若未传图片，展示纯文本提问。
  2. **普通助手气泡 (`AssistantTextMessageItem`)**：
     * 用于普通聊天或绘图过程中的思维链反馈，支持文本换行与代码块。
  3. **ATBDraw 结果对比卡片 (`DrawResultCard`)**：
     * 双列并排对比展示：左侧 `Before (原图)`，右侧 `After (精修效果)`。
     * 图片支持保持长宽比缩放展示，边缘圆角 `8px`。
     * 卡片下方信息栏：
       * 模板标签：如 `[全身显瘦]`、`[双频磨皮]`；
       * 性能耗时：如 `耗时: 1.2s`；
       * 动作工具栏：`[🔍 放大查看]`、`[💾 另存为]`、`[↺ 以此结果微调]`。
  4. **内联错误卡片 (`ErrorResultCard`)**：
     * 当任务因网络、参数或模型原因执行失败时，在对话流中原地展示柔和红色提示卡片（`#fff2f2`, 边框 `#ffcdd2`, 文字 `#d32f2f`）。
     * 显示详细失败信息，并提供 `[↺ 重试]` 按钮，避免中断用户的对话节奏。

### 3.3 底部可插拔 Footer 栏 (`FooterDock`)
吸附于中央主区域底部，采用外层悬浮式容器设计（圆角 16px、背景纯白 `#ffffff`、柔和边框与阴影），包含两层结构：

#### 1. 上层：插件动态控制栏 (`PluginControlBar`)
* **状态 A：纯文本通用模式（默认态）**：
  * 仅显示 `[+ 载入插件]` 按钮。点击弹出轻量选择菜单，支持载入 `ATBDraw (图像生成)`。
* **状态 B：已载入 ATBDraw 插件态**：
  * **插件胶囊标签**：显示 `[🖼️ 图像生成 (ATBDraw) ✕]`。点击 `✕` 即可卸载插件恢复通用文本模式。
  * **模型选择器 (Model Dropdown)**：`Seedream 4.5`、`Flux.1`、`SDXL`、`Mock Adapter`。
  * **比例选择器 (Aspect Ratio Dropdown)**：`自动`、`1:1`、`16:9`、`9:16`、`3:4`。
  * **艺术风格弹出浮层 (`StylePopover`)**：
    * 按钮文案随当前选中风格动态更新（如 `🎨 人像摄影 ∧`）。
    * 点击向上弹出一个漂亮的网格浮层（完全还原豆包体验）：人像摄影、电影写真、中国风、动漫、3D渲染、赛博朋克、水墨画、油画、古典、水彩画等。
  * **修图模板下拉框 (Template Selector)**：
    * 绑定 ATBDraw 的核心模板：`智能全身显瘦塑形`、`双频原生磨皮`、`面部立体轮廓微雕`、`服装边缘防畸变锁定`。

#### 2. 下层：输入交互栏 (`PromptInputBar`)
* **`+` 图片附件按钮**：
  * 支持文件弹窗选取图片，同时整栏支持外部拖入图片文件。
  * 选中后在文本框内部左侧插入微型图片 Chip，附带删除角标 `✕`。
  * **多轮对话图片策略**：若用户未选择图片，不强制阻断，直接允许发送纯文本进行自然追问与交互。
* **自适应多行输入框 (`AutoResizingTextEdit`)**：
  * 高度随文字行数在 `40px` 至 `120px` 之间弹性伸缩。
  * 占位文案：“输入描述或人像修图意图...”。
  * 快捷键：`Enter` 发送；`Shift+Enter` 换行。
* **发送/停止按钮**：
  * 常规状态：蓝色圆形发送图标按钮。
  * 执行中状态：转为旋转加载动效或停止按钮。

### 3.4 设置弹窗 (`SettingsDialog`)
模态对话框，支持配置并热更新全局 LLM API 参数：
* **Provider**：OpenAI / DeepSeek / Ollama / Local。
* **Base URL**：例如 `https://api.openai.com/v1`。
* **API Key**：密码掩码输入，支持明文切换；安全策略保障：不以明文形式打印至终端与运行日志中。
* **Model**：如 `gpt-4o`、`deepseek-chat`。
* **Temperature**：滑动条（0.0 ~ 1.0）。
* **操作按钮**：`测试连接`、`保存`、`取消`。保存时自动持久化至 `configs/config.yaml` 并热更新当前运行期单例。

---

## 4. 数据模型与存储架构设计 (Data Models & Storage Schema)

### 4.1 本地文件存储与 SQLite 表设计
所有持久化资产分为两大载体：
1. **生成图片存储路径**：`data/generated_images/{uuid}.png`，自动创建目录并保存高质量生成图。
2. **SQLite 数据库**：`data/atbmind.db`（与 `TemplateStore` 保持同一数据库实例）。

```sql
-- 会话元数据表
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    active_plugin_id TEXT,             -- NULL 表示通用纯文本会话，'draw' 表示 ATBDraw
    plugin_state TEXT,                  -- JSON: {model, aspect_ratio, style_id, template_id}
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

-- 消息流记录表
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,                -- 'user' | 'assistant' | 'system'
    content TEXT NOT NULL,             -- 提示词或回复文本
    attachment_path TEXT,              -- 关联的原图文件本地路径 (可为空)
    plugin_id TEXT,                    -- 执行此消息的插件 ID (如 'draw', 可为空)
    plugin_payload TEXT,               -- JSON: {before_img, after_img, plan, report, elapsed_seconds}
    created_at REAL NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session_time ON messages(session_id, created_at ASC);
```

### 4.2 Pydantic 核心数据类 (`atbmind_core/plugins/schemas.py`)

```python
class SessionRecord(BaseModel):
    session_id: str
    title: str = "新对话"
    active_plugin_id: Optional[str] = None   # 默认纯文本会话
    plugin_state: Dict[str, Any] = Field(default_factory=dict)
    created_at: float
    updated_at: float

class MessageRecord(BaseModel):
    message_id: str
    session_id: str
    role: str  # 'user' | 'assistant'
    content: str
    attachment_path: Optional[str] = None
    plugin_id: Optional[str] = None
    plugin_payload: Optional[Dict[str, Any]] = None
    created_at: float

class PluginUISpec(BaseModel):
    plugin_id: str
    display_name: str
    icon: str
    supports_attachments: bool = True
    attachment_types: List[str] = Field(default_factory=lambda: [".png", ".jpg", ".jpeg", ".webp"])
    models: List[str] = Field(default_factory=list)
    aspect_ratios: List[str] = Field(default_factory=list)
    styles: List[Dict[str, str]] = Field(default_factory=list)
    templates: List[TemplateMetadata] = Field(default_factory=list)
```

---

## 5. 插件协议与异步交互流 (Plugin Protocol & Async Flow)

### 5.1 插件扩展契约
`ATBMindPlugin` 基类扩展 `get_ui_spec()` 方法：
* `DrawPlugin.get_ui_spec()` 返回声明的参数字典；
* 宿主 `FooterDock` 根据 `get_ui_spec()` 动态装配风格、模型及模板；
* 结果渲染通过 `DrawResultCard` 独立解耦实现，宿主仅传递结构化 `plugin_payload`。

### 5.2 异步执行时序 (`GenerationWorker` & `TitleWorker`)

```mermaid
sequenceDiagram
    autonumber
    actor User as 用户
    participant UI as ATBMindMainWindow
    participant Store as SessionStore (SQLite)
    participant Worker as GenerationWorker (QThread)
    participant TitleW as TitleWorker (QThread)
    participant Core as Completer / Planner / Dispatcher
    participant Plugin as DrawPlugin (Adapter)

    User->>UI: 点击发送 (输入内容 + 可选图片附件)
    UI->>Store: 插入 User MessageRecord
    UI->>UI: 在 ChatStream 渲染 User 气泡与 Loading 动效卡片
    
    alt 若是本会话的首条消息
        UI->>TitleW: 启动后台异步生成标题
        TitleW->>Core: 请求 LLM 生成 4~8 字对话摘要
        TitleW-->>UI: Signal: title_generated(new_title)
        UI->>Store: 更新 SessionRecord.title
        UI->>UI: 实时刷新 Sidebar 会话项与 Header 标题
    end

    UI->>Worker: 启动异步线程 (prompt, img_path, plugin_id, plugin_state)
    activate Worker
    alt 挂载了 ATBDraw 且包含生图需求
        Worker->>Core: Layer 1 意图补全 (提取槽位与模板关联)
        Worker->>Core: Layer 2 编排 WorkflowPlan
        Worker->>Core: Layer 3 执行 Dispatcher + Plugin
        Core->>Plugin: execute_step() 渲染生成并保存到 data/generated_images/
        Plugin-->>Worker: 返回 WorkflowExecutionReport & 生成图像路径
        Worker-->>UI: Signal: finished(report, result_img_path)
    else 纯文本会话或普通追问
        Worker->>Core: 调用 LLMClient 进行自然语言回复
        Worker-->>UI: Signal: text_finished(reply_content)
    end
    deactivate Worker

    alt 成功
        UI->>Store: 插入 Assistant MessageRecord
        UI->>UI: 移除 Loading，替换为 DrawResultCard 或文本气泡
    else 异常失败
        Worker-->>UI: Signal: failed(error_message)
        UI->>UI: 移除 Loading，原地插入 ErrorResultCard (显示错误与重试按钮)
    end
    UI->>UI: 自动平滑滚动至最新
```

---

## 6. 关键技术决策 (Key Decisions from Grill Review)

在方案正式实施前，通过专项评审明确了如下 11 项技术决策：
1. **会话标题提炼**：首条消息发送后，通过独立的后台轻量任务调用 LLM 异步生成会话摘要标题，不阻塞主对话流。
2. **多轮原图复用策略**：多轮会话中图片为可选输入。无图时支持普通文本追问与交互，不强制要求每轮重复传图。
3. **内联错误处理 UX**：生图或大模型失败时，采用内联错误卡片（带有重试按钮）展示在对话流内，状态栏辅以简短提示，不打断用户操作。
4. **视觉规范**：专一适配 Apple HIG 浅色模式（Light Theme），集中精力打磨浅色下的高质感排版、圆角与阴影。
5. **新建会话默认行为**：新建会话默认启动为通用文本对话模式（无插件挂载），用户可在 FooterDock 中按需载入 ATBDraw。
6. **会话切换状态保留**：每个会话的插件状态（模型、比例、风格、模板）完整写入 `SessionRecord.plugin_state`，切换会话时精准复原。
7. **图片持久化定位**：生成图统一存放于本地专用目录 `data/generated_images/`，数据库仅存储文件绝对路径，保证 DB 体积轻量。
8. **应用打包范畴**：阶段重点在于打造高质量的 PySide6 桌面主程序 `apps/atbmind_desktop/main.py`，保持轻便与高度可测性。
9. **上下文管理**：对话历史窗口截断交由底层 Completer / LLMClient 自治处理，UI 保持全量历史展现。
10. **安全与日志隔离**：API Key 在设置界面中使用密码掩码，代码中严禁明文打印至运行日志与标准输出。
11. **严格顺序里程碑**：M1 (存储) -> M2 (插件契约与卡片) -> M3 (UI 构建) -> M4 (异步全链路与测试)，前序里程碑全绿后方可推进下一阶段。

---

## 7. 测试与质量保证策略 (Testing & Quality Strategy)

1. **会话存储单元测试 (`tests/test_session_store.py`)**：
   - 验证 Session 创建、按最新时间降序获取、修改标题；
   - 验证 Message 顺序追加、按会话 ID 隔离检索；
   - 验证级联删除：删除 Session 时对应所有 Messages 彻底清理。
2. **配置持久化测试 (`tests/test_config.py`)**：
   - 测试更新并回写 `configs/config.yaml`；
   - 保证环境变量与文件配置的正确继承与重写。
3. **桌面端 PySide6 自动化集成测试 (`tests/test_atbmind_desktop.py`)**：
   - 使用 `pytest-qt` 的 `qtbot`；
   - 验证窗口各组件初始化（Sidebar、ChatStream、FooterDock、SettingsDialog）；
   - 模拟用户点击 `+ 新对话`、切换会话；
   - 模拟上传图片附件并发送，验证 `GenerationWorker` 完成后卡片正确出现在 `ChatStream` 中；
   - 验证在设置弹窗中修改 LLM 参数并成功保存。
4. **向后兼容验证**：
   - 确保原有的 52 项单元测试 100% 保持绿色通过。

---

## 8. 实施里程碑计划 (Implementation Roadmap)

| 阶段 | 核心任务 | 交付成果 | 验收门禁 |
| :--- | :--- | :--- | :--- |
| **M1: 存储与配置持久化基石** | 实现 `SessionStore` (SQLite 表结构与 CRUD)，并在 `atbmind_core/config.py` 实现配置双向写入保存。 | `session_store.py` + 完整持久化单元测试 | `pytest tests/test_session_store.py` 100% 通过 |
| **M2: 插件 UI 契约与 ATBDraw 卡片适配** | 扩展 `PluginUISpec` 契约，在 `plugins/draw` 中开发 `DrawResultCard` 对比卡片与 UI 规格声明。 | 插件 UI 契约规范与测试卡片 | `pytest tests/test_plugin_ui.py` 100% 通过 |
| **M3: 核心桌面界面与交互组件构建** | 构建 `SidebarWidget`、`ChatStreamView`、`FooterDock`、`StylePopover` 及 `SettingsDialog`；组装 `ATBMindMainWindow`。 | `apps/atbmind_desktop/` 完整 UI 视觉与骨架 | 各独立 Widget 单元测试通过，主窗口成功无错拉起 |
| **M4: 异步流串联与端到端自动化测试** | 接入 `GenerationWorker` 与 `TitleWorker`，串联多轮对话流、图片附件装配与持久化加载，编写 `qtbot` 全量测试。 | 52+ 个全绿自动化测试，可启动的桌面主程序 | `pytest tests/` 所有用例全绿通过，端到端完整闭环 |
