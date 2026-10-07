# ATBMind RobotRole & Skill 架构升级设计规范 (Design Spec)

**日期**：2026-10-07  
**状态**：已批准 (Approved)  
**目标**：彻底废除旧的 Plugin（插件）抽象，在精简的 Harness Loop 内核之上建立现代化的 RobotRole（专家角色）与 Skill（技能）架构，支持无缝导入 GitHub 开源技能库，并通过 Leader + Specialist Subagents 协同完成复杂专业任务。

---

## 1. 背景与设计目标

### 1.1 现状与痛点
1. **架构割裂**：此前系统拥有旧版的三层状态机插件管线（`Completer -> Planner -> Dispatcher`）与新引入的 Pi 风格轻量级微内核（`Harness Loop`），代码中存在双轨逻辑。
2. **概念陈旧**：Plugin 概念过重，偏向系统级静态扩展，与现代 Agent 生态中以“专家角色（Persona / Role）”及“动态技能库（Skills）”为核心的设计范式不符。
3. **缺乏开源生态兼容**：无法直接复用 GitHub 上丰富的基于 `SKILL.md` 规范的 Agent 技能包。

### 1.2 核心目标
1. **去 Plugin 化**：全面移除 `ATBMindPlugin`、`PluginRegistry` 等插件体系，重构为 **`RobotRole`（专家角色）** 与 **`Skill`（技能）**。
2. **三层清晰分层**：
   * **底座层 (Harness Loop Core)**：极简的 `agent_loop` 状态机，负责流式生成、Turn 调度、工具执行、Steering 注入与取消中断。
   * **角色层 (RobotRole)**：拥有独立人设性格（Personality）、领域 System Prompt、专属模型配置，持有一个或多个 Skill。
   * **技能层 (Skill)**：标准化目录包，兼容开源 `SKILL.md`（Prompt 指引）+ `tools.py`（AgentTool 执行体）。
3. **团队主从编排 (Team & Subagents)**：
   * 默认由主协调员 `coordinator` 负责与用户交互，具备元工具 `delegate_task`；
   * 需要专业能力时，自主派发子任务给特定专家（如 `draw_expert`），专家在其独立子循环中闭环调用 Skills 完成任务并返回成果。
4. **Draw 能力平滑迁移**：原 `DrawPlugin` 完整转变为 `draw_expert` 角色及其挂载的 `image_generation` 技能，保持人像微调、生图与模板能力不降级。

---

## 2. 总体架构与系统分层

```
                                ┌──────────────────────┐
                                │   User / UI Client   │
                                └──────────┬───────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              RobotTeam (团队编排)                                │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         Coordinator (主协调员)                           │   │
│   │   - System Prompt (内置团队专家花名册与协同逻辑)                              │   │
│   │   - Meta Tool: delegate_task(role_id, task_description)                 │   │
│   └────────────────────────────────────┬────────────────────────────────────┘   │
│                                        │ (Subagent 派发)                         │
│                     ┌──────────────────┴──────────────────┐                     │
│                     ▼                                     ▼                     │
│   ┌─────────────────────────────────┐   ┌───────────────────────────────────┐   │
│   │   Draw Specialist (draw_expert) │   │    Coding Specialist (可扩展)      │   │
│   │   - 视觉精修人设与风格偏好            │   │    - 编码与调试人设                   │   │
│   │   - 挂载 Skill: [image_gen]     │   │    - 挂载 Skill: [coding]         │   │
│   └─────────────────────────────────┘   └───────────────────────────────────┘   │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                                         ▼ (驱动执行)
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           Harness Loop Core (内核)                              │
│   - atbmind_core/harness/loop.py: agent_loop (纯状态机)                         │
│   - atbmind_core/harness/session.py: AgentSession (会话与上下文管理)              │
│   - atbmind_core/harness/tools/base.py: AgentTool (最小可执行单元)               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 规范定义与数据模型

### 3.1 技能规范 (Skill Standard: A + C 融合)
每个 Skill 存放在 `skills/<skill_id>/` 目录下，包含说明文档与工具实现：

```text
skills/image_generation/
├── SKILL.md                 # 遵循开源规范的技能元数据与提示词指南
└── tools.py                 # 导出一组 AgentTool 子类
```

#### A. `SKILL.md` 格式规范
```markdown
---
name: image_generation
description: 高质量人像与艺术图片生成及多风格修图技能
version: 1.0.0
tags:
  - image
  - portrait
  - draw
---

# Image Generation & Retouching Guidelines
在调用生图或微调工具时，请遵循以下领域规范：
1. 分析用户意图是否属于人像美化、瘦身、磨皮或背景重绘。
2. 若涉及人像修图，调用 refine_image 并优先锁定服装边缘。
```

#### B. 数据模型 (`atbmind_core/skills/schema.py`)
```python
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from atbmind_core.harness.tools.base import AgentTool

class SkillMetadata(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)

class Skill:
    metadata: SkillMetadata
    domain_prompt: str
    tools: List[AgentTool]
    skill_dir: str
```

### 3.2 角色规范 (RobotRole Standard)
角色定义存放在 `roles/<role_id>/role.yaml`：

```yaml
role_id: "draw_expert"
name: "视觉绘图与精修专家"
description: "精通人像摄影、修图、美颜微调和多风格画面渲染的资深设计师"
personality: "富有艺术审美，注重光影、构图与肤质细节，语气专业优雅"
system_prompt: |
  你是团队中的核心视觉艺术与图像修图专家。
  你擅长理解用户的自然语言视觉意图，并自主使用持有的绘图工具完成高水准渲染。
skills:
  - image_generation
model: "gpt-4o"
temperature: 0.7
```

#### 数据模型 (`atbmind_core/roles/schema.py`)
```python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from atbmind_core.skills.schema import Skill

class RobotRole(BaseModel):
    role_id: str
    name: str
    description: str
    personality: str = ""
    system_prompt: str
    skills: List[str] = Field(default_factory=list)  # 挂载的 Skill 名称列表
    model: Optional[str] = None
    temperature: Optional[float] = None
    
    def build_system_prompt(self, loaded_skills: Dict[str, Skill]) -> str:
        """合成角色的完整 System Prompt：角色定位 + 性格 + 各 Skill 领域指南"""
        parts = [self.system_prompt.strip()]
        if self.personality:
            parts.append(f"\n【性格与对话风格】\n{self.personality.strip()}")
        
        domain_prompts = []
        for s_id in self.skills:
            if s_id in loaded_skills and loaded_skills[s_id].domain_prompt:
                domain_prompts.append(f"### Skill 指南 [{s_id}]\n{loaded_skills[s_id].domain_prompt.strip()}")
        
        if domain_prompts:
            parts.append("\n【专业技能指引】\n" + "\n\n".join(domain_prompts))
            
        return "\n\n".join(parts)
```

---

## 4. 运行时协同与 Subagent 派发机制

### 4.1 Coordinator 与 `DelegateTaskTool`
1. **自动感知**：团队启动时，`RobotTeam` 扫描所有就绪专家，动态向 Coordinator 注入专家名录。
2. **委派工具**：
   ```python
   class DelegateTaskInput(BaseModel):
       role_id: str = Field(..., description="目标专家角色的 ID，如 'draw_expert'")
       task_description: str = Field(..., description="委派给该专家的具体任务和详细上下文要求")

   class DelegateTaskTool(AgentTool):
       name = "delegate_task"
       description = "将专业领域的复杂任务委派给团队内的专家角色执行"
       parameters_schema = DelegateTaskInput
   ```
3. **隔离与执行流**：
   * 为目标角色构建全新的 `AgentContext`（装配该专家的专属 System Prompt 与 Skills 工具集）；
   * 启动独立的 `agent_loop(...)`；
   * 将子循环的中间事件带上 `metadata={"origin_role": role_id}` 标签实时透传给上层 Event Listener / UI；
   * 子循环结束后，将专家的最终答复与产物（如 `image_path`）包装为 `ToolResult` 返回给 Coordinator。

---

## 5. Draw 专家迁移与桌面端集成

### 5.1 技能模块：`skills/image_generation/`
* `SKILL.md` 包含原有 `plugins/draw/prompts/injection.py` 沉淀的人像黄金法则、多风格提示词后缀、常用模板说明。
* `tools.py` 导出：
  * `GenerateImageTool`
  * `RefineImageTool`
  * `SearchTemplatesTool`
  内部直接调用现有的图片适配器体系（`plugins/draw/adapters/`）。

### 5.2 角色定义：`roles/draw_expert/role.yaml`
注册为核心专家角色。

### 5.3 桌面端 `GenerationWorker` 重构
* 移除 `active_plugin_id == "draw"` 的旧三层状态机分支；
* Worker 内部统一持有 `RobotTeam` 与 `AgentSession`；
* 用户在界面的 Style / Aspect Ratio / Template 勾选状态，作为初始 Prompt 补充或 Steering 上下文注入；
* 工具产生的图片结果通过 Worker 的 `finished(session_id, report, image_path)` 信号传递，Chat 界面原生显示。

---

## 6. 清理与废弃计划 (Deprecation)

1. **废弃目录与类**：
   * 废除 `atbmind_core/plugins/` 全部文件（`base.py`, `registry.py`, `exceptions.py`）；
   * 废除 `atbmind_core/engine/completer.py`, `planner.py`, `dispatcher.py`；
   * 将存储用到的基础数据结构平移至 `atbmind_core/storage/schemas.py`；
2. **配置更新**：
   * `configs/app_config.py` 中的 `plugins` 配置平滑升级为 `roles` 与 `skills`。

---

## 7. 文档与 README 理念更新

在所有核心代码重构与功能验证全部完成后，更新根目录下的 `README.md`，全面反映新的架构与理念：
1. **项目定位与理念**：阐明以精简 Harness Loop 为底座、以专才角色（RobotRole）为载体、以模块化兼容开源（Skill）为能力的现代智能体设计理念。
2. **架构图与分层**：更新最新的系统分层图（Harness Loop -> RobotRole Team -> Skills）。
3. **扩展与导入指南**：说明如何无缝导入 GitHub 开源技能（`skills/`）以及如何通过 YAML 自定义新的专家角色（`roles/`）。

---

## 8. 测试与质量保证

1. **`tests/test_skills.py`**：测试 `SKILL.md` 解析、YAML Frontmatter 校验、`tools.py` 动态加载。
2. **`tests/test_roles.py`**：测试 `role.yaml` 加载、角色 System Prompt 合成、`delegate_task` Subagent 派发执行。
3. **`tests/test_draw_robot_role.py`**：端到端验证 `draw_expert` 调用生图工具产出图片及元数据。
4. **`tests/test_desktop_workers_roles.py`**：验证桌面端多线程 Worker 在角色编排下的信号发射。
5. **回归测试**：全量执行 `conda run -n ATBMind python -m pytest tests/`，保证测试 100% 通过。

