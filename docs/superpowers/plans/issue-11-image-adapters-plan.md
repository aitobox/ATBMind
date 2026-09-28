# Issue #11 Plan: 实现绘图模型适配器 (MockImageAdapter 与 CloudAPIAdapter)

## Implementation Steps
1. **Base Adapter Contract (`plugins/draw/adapters/base.py`)**:
   - 定义 `ImageAdapterResponse` 与抽象基类 `ImageModelAdapter`，以及工厂函数 `create_image_adapter()`。
2. **Mock Adapter (`plugins/draw/adapters/mock_adapter.py`)**:
   - 实现 `MockImageAdapter`，在图像中写入水印与形变框标记元数据，保证离线耗时 `< 50ms`。
3. **Cloud Adapter (`plugins/draw/adapters/cloud_adapter.py`)**:
   - 实现 `CloudAPIAdapter`，封装 `httpx.Client` 云端图像生成/编辑请求与 `b64_json`/`url` 响应解析。
4. **Integrate with `DrawPlugin` (`plugins/draw/plugin.py`)**:
   - 支持配置动态切换 `mock` / `cloud` 适配器。
5. **Unit Tests (`tests/test_draw_adapters.py`)**:
   - 测试 `MockImageAdapter` 延迟 `< 50ms`、水印与形变框元数据、`CloudAPIAdapter` 请求组装与响应解析、以及 `DrawPlugin` 动态切换。
