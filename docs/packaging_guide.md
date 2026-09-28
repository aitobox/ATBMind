# ATBDraw 跨平台原生打包与发布指南

本指南介绍如何使用 Nuitka 将 `ATBDraw` 桌面端应用（基于 PySide6 + ATBMind 核心与插件体系）一键打包为免 Python 环境依赖的独立原生可执行文件。

---

## 1. 打包前置准备

### 1.1 Python 环境与编译工具链
- **Python**: 3.12+ (使用 Conda 或 venv)
- **编译工具**:
  - **macOS**: Xcode Command Line Tools (`xcode-select --install`)
  - **Windows**: Visual Studio 2022 (Community 版，勾选 C++ 桌面开发) 或 MinGW64
  - **Linux**: `gcc` / `g++` (`sudo apt-get install build-essential`)
- **Nuitka**:
  ```bash
  pip install nuitka zstandard ordered-set
  ```

---

## 2. 一键打包命令

在项目根目录下执行打包脚本：

```bash
# 1. 检查构建参数与依赖（Dry Run）
bash scripts/build_nuitka.sh --dry-run

# 2. 执行完整独立打包
bash scripts/build_nuitka.sh

# 3. 指定输出目录（可选）
bash scripts/build_nuitka.sh --output-dir=/path/to/custom_dist
```

### 关键编译参数说明
- `--standalone`: 生成包含独立 Python 解释器运行时的免安装发布目录。
- `--enable-plugin=pyside6`: 自动分析并包含 PySide6/Qt6 动态库、字体引擎及 `platforms` 插件（如 `libqcocoa.dylib` 或 `qwindows.dll`）。
- `--include-package=atbmind_core` 与 `--include-package=plugins`: 打包核心推理引擎与领域插件。
- `--include-data-files`: 复制 `seed_templates.json` 种子模板元数据库与 `configs/config.yaml` 基础配置。
- `--macos-create-app-bundle` (macOS 专属): 自动封装为标准的 macOS 原生 `.app` 应用程序包 (`dist/ATBDraw.app`)。

---

## 3. 构建产物验证与冒烟测试检查项

在构建完成后，可在无 Python 环境的干净系统下执行以下冒烟测试项：

### 3.1 命令行版本检查
```bash
# macOS
./dist/ATBDraw.app/Contents/MacOS/ATBDraw --version
# 或独立目录二进制
./dist/main.dist/ATBDraw --version

# Windows
dist\main.dist\ATBDraw.exe --version
```
**期望输出**：
```
ATBDraw 0.1.0 (ATBMind Core 0.1.0)
```

### 3.2 界面交互与离线出图冒烟项
1. **启动测试**: 双击启动应用程序，主界面正常渲染，无动态库缺失报错。
2. **图片拖拽测试**: 拖入任意 JPG/PNG 人像图片，原图卡片正常展示图片缩略图。
3. **心眼生成测试**:
   - 在底栏输入口语指令：“把右边的人稍微变瘦，衣服别走样”。
   - 点击“心眼生成 ✨”，离线状态下 100ms 内完成意图理解并呈现修后效果。
4. **抽屉微调测试**:
   - 右侧“结果侧微调抽屉”展示已调用的模板与参数滑块。
   - 拖动强度滑块，点击“微调重新生成 ⚡”，画布即时刷新。
5. **另存为测试**: 点击“另存为 💾”，成功保存输出的 PNG 文件。
