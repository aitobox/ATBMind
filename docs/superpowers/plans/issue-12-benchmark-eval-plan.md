# Issue #12 Plan: 构建 50 组人像精修端到端基准测试集并验证匹配准确率 (>90%)

## Implementation Steps
1. **Enhance `WorkflowPlanner._select_candidates()` (`atbmind_core/engine/planner.py`)**:
   - 增加基于 `draft.intent_category`、`draft.parameters` 关键词与描述的相关性打分排序 (`score_template_relevance`)，提升多意图与细粒度模板检索召回率。
2. **Create 50-Case End-to-End Benchmark Suite (`tests/benchmarks/benchmark_draw.py`)**:
   - 定义 50 组代表性人像精修口语输入、预期意图类别、预期命中模板及依赖拓扑关系。
   - 实现端到端基准运行器 `run_draw_benchmark()`，串联 `LatentIntentCompleter`、`WorkflowPlanner`、`SlotDispatcher` 与 `DrawPlugin`，输出详细评测报告并断言 `overall_accuracy >= 0.90`。
3. **Verification**:
   - 运行 `PYTHONPATH=. conda run -n ATBMind pytest tests/benchmarks/benchmark_draw.py` 及全量 `pytest tests/`。
