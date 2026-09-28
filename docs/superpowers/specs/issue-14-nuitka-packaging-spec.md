# Issue #14 Spec: 编写 Nuitka 跨平台原生打包脚本与一键发布流程

## 1. 目标 (Objective)
编写基于 Nuitka 的桌面端跨平台打包脚本 (`scripts/build_nuitka.sh`) 与打包构建文档 (`docs/packaging_guide.md`)，并为 `apps/atb_draw_desktop/main.py` 增加 CLI 参数支持（如 `--version`、`--headless`、`--help`），确保无需 Python 环境即可独立分发与运行。

## 2. 脚本与配置设计 (`scripts/build_nuitka.sh`)
- 编译入口：`apps/atb_draw_desktop/main.py`
- 关键编译参数：
  - `--standalone`：打包为独立分发目录，内嵌 Python 运行时
  - `--enable-plugin=pyside6`：自动打包 PySide6 及 Qt 动态库与插件 (platforms/qminimal, styles)
  - `--include-package=atbmind_core`、`--include-package=plugins`
  - `--include-data-files=plugins/draw/templates/seed_templates.json=plugins/draw/templates/seed_templates.json`
  - `--include-data-files=configs/config.yaml=configs/config.yaml`
  - macOS 专属参数：`--macos-create-app-bundle`、`--macos-app-name=ATBDraw`
  - 输出路径：`dist/`
- 支持 `--dry-run` 模式快速校验参数与依赖环境。

## 3. CLI 支持 (`apps/atb_draw_desktop/main.py`)
- 支持 `python3 apps/atb_draw_desktop/main.py --version` 输出版本号 `ATBDraw 0.1.0 (ATBMind Core 0.1.0)` 并正常退出。
