# Issue #11 Spec: 实现绘图模型适配器 (MockImageAdapter 与 CloudAPIAdapter)

## 1. 目标 (Objective)
在 `ATBMind-Draw` 插件中实现底层图像模型适配器架构，提供无需 GPU、离线毫秒级响应的 `MockImageAdapter` 以及对接云端扩散模型 API (SiliconFlow / OpenAI Images) 的 `CloudAPIAdapter`，支持通过配置动态切换。

## 2. 模块设计
1. **`plugins/draw/adapters/base.py`**:
   - `ImageAdapterResponse`：标准化图像渲染输出模型（`success`, `image_bytes`, `image_url`, `applied_template_id`, `applied_slots`, `adapter_type`, `latency_ms`, `metadata`）。
   - `ImageModelAdapter(ABC)`：定义 `render_step(template_id, slots, context) -> ImageAdapterResponse` 抽象接口。
   - `create_image_adapter(config)`：根据 `config.get("adapter", "mock")` 动态实例化 `MockImageAdapter` 或 `CloudAPIAdapter`。
2. **`plugins/draw/adapters/mock_adapter.py`**:
   - `MockImageAdapter`：生成带 SVG/PNG 字节头、形变包围盒与水印标记元数据的图像二进制数据，单次耗时 `< 5ms`（满足 `< 50ms` 验收指标）。
3. **`plugins/draw/adapters/cloud_adapter.py`**:
   - `CloudAPIAdapter`：组装 Inpaint / 图像编辑请求载荷（含 `model`, `prompt`, `slots`, `mask_region`, `response_format`），通过 `httpx.Client` 调用云端端点并解析 `b64_json` 二进制或 `url`。
4. **集成 `DrawPlugin`**:
   - `DrawPlugin.initialize(config)` 初始化当前激活的 `adapter`，并在 `execute_workflow_step` 中调用 `self.adapter.render_step(...)`。
