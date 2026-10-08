# Issue #64 Spec: 强化 Coordinator 调度准则、任务改写与收口闭环

**Issue:** [#64](https://github.com/aitobox/ATBMind/issues/64)  
**Parent Epic:** [#62](https://github.com/aitobox/ATBMind/issues/62)  
**Status:** Approved (Autonomous Decision Rule >= 90%)  
**Branch:** `agent/issue-64-coordinator-rules-closure`  

---

## 1. 目标与背景 (Objective & Background)

借鉴 TencentCloud/Octop 主持人（Host/Coordinator）核心约束设计：
主持人严禁自己干重活（禁止生图、写文件、执行系统命令等重型工具），必须将用户原话消化后改写为专用的结构化任务说明书派发给专家角色（Anti-Pass-Through 准则），并在专家执行完成后通过 `compose_followup` 进行闭环收口（仅判断是否收工并输出不超过 3 句短总结，严禁复述专家上墙的原文）。

---

## 2. 架构设计与核心契约 (Architecture & Contracts)

### 2.1 Coordinator 工具白名单拦截机制 (Tool Whitelist Enforcement)
在 `atbmind_core/roles/team.py` 中：
- 定义 `COORDINATOR_ALLOWED_TOOLS = {"delegate_task", "list_roles", "get_current_time", "current_time", "time", "memory_query", "memory_recall", "memory_store", "context_search"}`
- 增加 `ListRolesTool` 并注册入 Coordinator 默认可用工具库。
- 当为 Coordinator 构造 Session (`create_coordinator_session`) 时，严格执行白名单过滤，剥离任何非白名单工具（例如 `generate_image`, `file_write`, `write_to_file`, `replace_file_content`, `run_command`, `bash` 等重型执行工具）。

### 2.2 Anti-Pass-Through 准则与 Prompt 强化
在 `roles/coordinator/role.yaml` 与 `roles/coordinator.json` 中：
- 显式注入 Anti-Pass-Through 约束：
  1. 严禁直接原样复制用户的原话转发给专家角色。
  2. 必须重写为包含【目标】、【边界约束】、【交付格式】的专业任务说明书。
  3. 主持人严禁直接干重活，所有专业工作必须委派。
- 在 `RobotTeam.build_coordinator_system_prompt()` 中动态附加 Anti-Pass-Through 与收口规范段落。

### 2.3 `compose_followup` 闭环收口函数
在 `atbmind_core/roles/delegation.py` 中：
- 实现 `compose_followup` 函数：
  ```python
  def compose_followup(
      role_id: str,
      role_name: str,
      task_description: str,
      subagent_result: str,
      max_sentences: int = 3,
  ) -> str:
      ...
  ```
  该函数在专家执行完毕后构造结构化收尾通知，指导 Coordinator 仅判断交付是否符合预期并生成最多 3 句收口结论。
- 在 `DelegateTaskTool.execute` 中集成 `compose_followup` 生成返回内容，并在 metadata 中标记 `followup_composed: True`。

### 2.4 测试验证策略
- 新建 `tests/test_coordinator_rules.py`：
  1. 测试白名单过滤：给 Coordinator 挂载重型工具后，实例化 session 时被自动剔除，仅保留白名单工具；
  2. 测试 `ListRolesTool`：正确返回当前所有可用专家列表；
  3. 测试 `compose_followup`：格式化收尾唤醒消息并保证不超过句数限制约束；
  4. 测试 Coordinator System Prompt 中包含 Anti-Pass-Through 规则关键字；
  5. 测试 `roles/coordinator.json` 与 `role.yaml` 数据一致性。

---

## 3. Implementation Task Checklist

- [x] Task 1: 编写单元测试 `tests/test_coordinator_rules.py` 覆盖白名单拦截、Prompt 注入与 `compose_followup`
- [x] Task 2: 实现 `ListRolesTool` 并加入 `atbmind_core/roles/delegation.py`
- [x] Task 3: 在 `atbmind_core/roles/team.py` 中实现 Coordinator 工具白名单过滤逻辑
- [x] Task 4: 更新 `roles/coordinator/role.yaml` 并生成 `roles/coordinator.json`，注入 Anti-Pass-Through 规则
- [x] Task 5: 在 `atbmind_core/roles/delegation.py` 实现 `compose_followup` 并在 `DelegateTaskTool` 中集成
- [x] Task 6: 运行 `tests/test_coordinator_rules.py` 与全量测试套件验证无回归
- [x] Task 7: 进行 grill-me 质量审计并准备代码评审
