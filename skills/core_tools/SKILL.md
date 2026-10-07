---
name: core_tools
description: Antigravity 核心系统工具包，涵盖精准文件查看/局部替换/写入、命令行与持久终端执行、任务与定时调度、交互式提问模态以及多智能体协同派发。
version: 1.0.0
tags:
  - system
  - filesystem
  - terminal
  - scheduler
  - subagents
  - interaction
---

# Antigravity Core Tools Guidelines

本技能包为智能体提供系统级操作能力，请在调用时严格遵循以下指导方针：

## 1. 文件系统操作规范
- **精准查看 (`view_file`)**：优先使用 `StartLine` 与 `EndLine`（1-indexed）进行区间切片读取，单次限制不超过 800 行与 45KB，避免向会话中载入超长大文件。
- **局部精细替换 (`replace_file_content`)**：严禁全量重写长文件。必须在指定的 `[StartLine, EndLine]` 行号窗口内进行精确匹配替换，确保 `TargetContent` 唯一存在。
- **文件写入与工件创建 (`write_to_file`)**：创建新文件时明确设定 `Overwrite` 或 `Append`；生成重要架构规划或代码报告时提供 `ArtifactMetadata`。

## 2. 命令行与任务治理规范
- **命令执行 (`run_command`)**：
  - 快命令将毫秒级同步返回输出；
  - 超过 `WaitMsBeforeAsync` 的耗时构建、测试或服务启动会自动切入后台，返回 `task_id`，日志流式落盘；
  - 针对需要共享上下文环境变量（如 `source`, `export`）的多步操作，指定统一的 `RequestedTerminalID`。
- **任务管理 (`manage_task`)**：可查询任务状态 (`status`)、杀死卡死进程 (`kill`) 或向进程输入交互响应 (`send_input`)。

## 3. 定时与调度规范
- **调度工具 (`schedule`)**：支持一次性延时定时器（`DurationSeconds`）与周期性 Cron（`CronExpression`），到期后将自动向上下文注入 `<SYSTEM_MESSAGE>`，无需轮询。

## 4. 多智能体协作与交互
- **子智能体协作 (`invoke_subagent`, `send_message`, `manage_subagents`)**：在独立上下文中派发子专家（如 `draw_expert` 或独立分身 `self`），避免 Token 污染。
- **交互式确认 (`ask_question`)**：遇到重大需求分歧或高危操作时，调用此工具向用户弹出单选/多选交互卡片进行决策确认。
