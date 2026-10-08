# Issue #64 Implementation Plan: 强化 Coordinator 调度准则、任务改写与收口闭环

> **Goal:** 落实 Issue #64 全部验收标准：剥离 Coordinator 重型执行工具，注入 Anti-Pass-Through 任务改写准则，实现 `compose_followup` 闭环收口函数，并通过全部单元测试。

**Branch:** `agent/issue-64-coordinator-rules-closure`  
**Spec:** `docs/superpowers/specs/issue-64-coordinator-rules-closure-spec.md`  

---

### Task 1: 编写单元测试 `tests/test_coordinator_rules.py` (TDD First)
- [x] 编写测试用例覆盖：
  - Coordinator 工具白名单剥离（添加重型工具如 `generate_image`、`file_write`，验证 session 仅保留白名单工具）
  - `ListRolesTool` 功能与元数据返回
  - `compose_followup` 格式化收口消息（验证最多 3 句短总结与防复述要求）
  - Anti-Pass-Through 提示词规则注入校验
- [x] 运行测试确认预期失败 (RED)

### Task 2: 实现 `ListRolesTool` 并加入 `atbmind_core/roles/delegation.py`
- [x] 在 `atbmind_core/roles/delegation.py` 中增加 `ListRolesTool`，继承 `AgentTool`
- [x] 在 `atbmind_core/roles/__init__.py` 中导出 `ListRolesTool`

### Task 3: 在 `atbmind_core/roles/team.py` 中实现 Coordinator 工具白名单过滤与工具装配
- [x] 定义 `COORDINATOR_ALLOWED_TOOLS`
- [x] 改造 `create_coordinator_session`：自动添加 `ListRolesTool` 和 `DelegateTaskTool`，过滤从 leader_role 继承的工具，剔除非白名单重型工具

### Task 4: 更新 `roles/coordinator/role.yaml` 与 `roles/coordinator.json`
- [x] 更新 `roles/coordinator/role.yaml` 中的 system_prompt，注入 Anti-Pass-Through 准则（禁止直接转发用户原话，必须改写包含目标、边界、交付格式的专业任务书；严禁自己干重活）
- [x] 创建/同步 `roles/coordinator.json`
- [x] 在 `RobotTeam.build_coordinator_system_prompt` 中动态集成 Anti-Pass-Through 核心指令

### Task 5: 在 `atbmind_core/roles/delegation.py` 实现 `compose_followup`
- [x] 实现 `compose_followup(role_id, role_name, task_description, subagent_result, max_sentences=3)`
- [x] 在 `DelegateTaskTool.execute` 中集成 `compose_followup` 构造返回内容与元数据

### Task 6: 验证与全量回归测试
- [x] 运行 `tests/test_coordinator_rules.py` 确认通过 (GREEN)
- [x] 运行全量测试套件 `pytest tests/` 确认 352 项测试 100% 通过无回归

### Task 7: grill-me 质量审计并推进至 reviewing 阶段
- [x] 核对所有验收标准与实现细节
- [x] 更新状态至 reviewing，准备交付 PR
