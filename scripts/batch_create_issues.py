import subprocess
import time
import sys

issues = [
    {
        "num": 10,
        "title": "整理并导入首期 300~500 条高频人像精修种子模板库",
        "label1": "feature",
        "label2": "priority: medium",
        "body": """### Objective
构建首发 Draw 插件的种子指令模板库，精选 300~500 条高频人像精修模板并转换为标准元数据格式。

### Scope & Requirements
- `plugins/draw/templates/seed_templates.json`：编写 300~500 条标准化模板
- 覆盖四大分类：人像修形 (body/waist/shoulder)、面部五官精修 (face/jaw/eyes)、质感光影 (skin/lighting)、衣物与背景防畸变联动 (cloth/background)
- 每条包含：唯一 template_id, name, category, keywords, target_scope, slot_definitions, dependencies
- 提供自动化校验脚本验证 JSON 结构与字段合法性

### Acceptance Criteria
- [ ] 包含不少于 300 条真实可用的精选模板元数据
- [ ] 所有模板 ID 唯一，关键词与槽位规范完整
- [ ] 能被中间件批量导入 SQLite 且零校验报错

### Verification Plan
```bash
python3 scripts/validate_templates.py plugins/draw/templates/seed_templates.json
```"""
    },
    {
        "num": 11,
        "title": "实现绘图模型适配器 (MockImageAdapter 与 CloudAPIAdapter)",
        "label1": "feature",
        "label2": "priority: medium",
        "body": """### Objective
在 Draw 插件中实现底层图像模型适配器架构，提供无 GPU 离线测试的 Mock 适配器与真实的云端 API 适配器。

### Scope & Requirements
- `plugins/draw/adapters/base.py`：定义 `ImageModelAdapter` 接口
- `plugins/draw/adapters/mock_adapter.py`：实现 `MockImageAdapter`，在图像上绘制水印标记与形变框，模拟即时返回
- `plugins/draw/adapters/cloud_adapter.py`：实现 `CloudAPIAdapter`，对接云端扩散模型 API (如 SiliconFlow / DALL-E)
- 支持通过配置动态切换 active adapter

### Acceptance Criteria
- [ ] 离线环境下通过 Mock 适配器能实现 < 50ms 端到端出图
- [ ] 真实适配器能正确组装 Inpaint/形变请求并返回图像二进制/URL
- [ ] 单测覆盖适配器接口一致性

### Verification Plan
```bash
pytest tests/test_draw_adapters.py
```"""
    },
    {
        "num": 12,
        "title": "构建 50 组人像精修端到端基准测试集并验证匹配准确率 (>90%)",
        "label1": "enhancement",
        "label2": "priority: medium",
        "body": """### Objective
建立针对 Draw 插件的端到端意图匹配与执行评估基准，量化验证大白话短句转模板组合的准确率。

### Scope & Requirements
- `tests/benchmarks/benchmark_draw.py`：整理 50 组真实场景的模糊修图口语（如“把右边的人稍微变瘦，衣服别走样”）
- 设定每组用例的期望命中模板组合与拓扑关系
- 自动化运行全流程，统计 Top-K 召回率、排序合理性指标
- 调优提示词工程，确保整体准确率 >= 90%

### Acceptance Criteria
- [ ] 包含 50 组覆盖全面、有代表性的人像修图测试用例
- [ ] 自动化评测报告输出命中率与错误样例分析
- [ ] 综合匹配准确率达到 90% 以上

### Verification Plan
```bash
pytest tests/benchmarks/benchmark_draw.py
```"""
    },
    {
        "num": 13,
        "title": "开发基于 PySide6 的极简桌面应用与结果侧微调抽屉",
        "label1": "feature",
        "label2": "priority: medium",
        "body": """### Objective
开发首个应用客户端 ATBDraw 桌面端 (PySide6)，实现拖拽传图、一键意图出图及侧边参数抽屉二次微调的完整人机协同闭环。

### Scope & Requirements
- `apps/atb_draw_desktop/main.py`：主程序入口与界面编排
- 界面布局：图片拖拽上传区、极简单行需求输入框、“心眼生成”触发按钮、修后图/对比图预览区
- 侧边抽屉：展示被调用的模板列表与参数滑块（如瘦身幅度: 12%）
- 用户调节滑块后，点击“微调重新生成”，直连 Layer 3 快速重跑

### Acceptance Criteria
- [ ] 界面交互流畅，符合“静默缺省 + 结果侧抽屉微调”理念
- [ ] 支持本地图片拖入与结果另存为
- [ ] 抽屉滑块调参与重跑逻辑工作正常

### Verification Plan
```bash
python3 apps/atb_draw_desktop/main.py
```"""
    },
    {
        "num": 14,
        "title": "编写 Nuitka 跨平台原生打包脚本与一键发布流程",
        "label1": "enhancement",
        "label2": "priority: low",
        "body": """### Objective
编写基于 Nuitka 的桌面端打包脚本，将 PySide6 客户端与 ATBMind 内核一键打包为免环境依赖的原生可执行文件。

### Scope & Requirements
- `scripts/build_nuitka.sh`：配置 Nuitka 编译参数 (含 Qt 插件、数据文件包含、排除无用模块)
- 支持跨平台 (macOS / Windows) 独立二进制分发
- 编写打包验证与冒烟测试检查项文档

### Acceptance Criteria
- [ ] 打包出的原生可执行文件在无 Python 环境的干净系统下可直接运行
- [ ] 启动速度正常，图片加载与推理调用功能完备
- [ ] 输出清晰的打包指南文档

### Verification Plan
```bash
bash scripts/build_nuitka.sh
./dist/ATBDraw --version
```"""
    }
]

for it in issues:
    num = it["num"]
    title = it["title"]
    print(f"Creating Issue {num}: {title}...")
    cmd = [
        "gh", "issue", "create",
        "--repo", "aitobox/ATBMind",
        "--title", title,
        "--body", it["body"],
        "--label", it["label1"],
        "--label", it["label2"]
    ]
    for attempt in range(5):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Created: {res.stdout.strip()}")
            time.sleep(1)
            break
        else:
            print(f"Attempt {attempt+1} failed: {res.stderr.strip()}, retrying in 2s...")
            time.sleep(2)
    else:
        print(f"Failed to create issue {num}")
        sys.exit(1)

print("All remaining issues created successfully!")
