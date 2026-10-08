# ATBMind Brand Mascot and Logo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 设计并生成 3D 盲盒黏土柴犬虚拟代言人形象，构建全套多分辨率品牌图标资源库（包括 macOS 原生 ICNS），并在桌面客户端及项目中全面替换应用图标、侧边栏 Logo、关于弹窗及文档。

**Architecture:** 
1. 通过 AI 生成母版 3D 盲盒小柴犬立绘与 Squircle 应用图标，编写 `scripts/generate_brand_assets.py` 进行 Lanczos 重采样输出 16px~1024px PNG 及 macOS 原生 `app_icon.icns`。
2. 在 `apps/atbmind_desktop/theme.py` 封装统一的 `BrandAssets` 提供者，统一调度与缓存多级 `QIcon`、头像 `QPixmap` 与立绘，并提供防御性降级逻辑。
3. 全面集成至 `main.py`（QApplication window icon）、`main_window.py`（主窗口图标）、`navigation_sidebar.py`（侧边栏品牌区域）、`settings_dialog.py`（关于卡片）及 `README.md`。

**Tech Stack:** Python 3.12, PySide6, Pillow (PIL), macOS `iconutil`, pytest.

**Spec:** [docs/superpowers/specs/2026-10-08-brand-mascot-and-logo-design.md](file:///Users/brainzhang/work/aitobox/ATBMind/docs/superpowers/specs/2026-10-08-brand-mascot-and-logo-design.md)

## Global Constraints

- 静态资源统一放置于 `resource/assets/brand/` 目录。
- 图像尺寸梯队：16×16, 32×32, 64×64, 128×128, 256×256, 512×512, 1024×1024 PNG 及 `app_icon.icns`。
- 图标风格符合 Apple HIG 连续曲率 Squircle 及微投影，透明底头像切图为 RGBA 模式。
- `BrandAssets` 类必须具备无崩溃降级保障，当静态资源缺失时自动回退为内嵌矢量图标。
- 自动化测试命令：`PYTHONPATH=src conda run -n ATBMind python -m pytest tests/` 保持 100% 通过。

## Review Focus

1. **资源文件不存在或损坏**：`BrandAssets.get_app_icon()` 在路径不存在时返回默认矢量 QIcon，不抛出异常破坏桌面启动。
2. **非 macOS 平台或缺少 iconutil**：`generate_brand_assets.py` 在无 macOS 环境时安全捕获并提供 fallback，避免生成流程中断。
3. **HiDPI / Retina 2x 屏幕缩放**：`get_mascot_avatar(size)` 需支持指定像素或 Retina 渲染，保持边缘光滑不失真。
4. **导航侧边栏折叠/展开动态适配**：侧边栏折叠时仅展示头像微标，展开时显示完整头像与品牌文字，不产生布局溢出。
5. **测试断言环境隔离**：单元测试断言所有规格图片存在且维度精准匹配，且不依赖 GUI 显示服务器（支持 headless 模式）。

---

### Task 1: 品牌代言人生成与多尺寸资产处理管线

**Files:**
- Create: `scripts/generate_brand_assets.py`
- Create: `resource/assets/brand/mascot_hero.png`
- Create: `resource/assets/brand/mascot_avatar.png`
- Create: `resource/assets/brand/app_icon_1024.png`
- Create: `resource/assets/brand/app_icon_512.png`
- Create: `resource/assets/brand/app_icon_256.png`
- Create: `resource/assets/brand/app_icon_128.png`
- Create: `resource/assets/brand/app_icon_64.png`
- Create: `resource/assets/brand/app_icon_32.png`
- Create: `resource/assets/brand/app_icon_16.png`
- Create: `resource/assets/brand/app_icon.icns`
- Test: `tests/test_brand_assets.py`

**Interfaces:**
- Consumes: None
- Produces: `resource/assets/brand/` 下全套品牌 PNG 与 ICNS 资产，供 `BrandAssets` 提供者读取。

- [ ] **Step 1: Write the failing test for brand assets existence and specifications**

```python
# tests/test_brand_assets.py
from pathlib import Path
from PIL import Image

BRAND_DIR = Path(__file__).resolve().parents[1] / "resource" / "assets" / "brand"

def test_brand_assets_files_exist_and_dimensions():
    required_pngs = {
        "mascot_hero.png": (1024, 1024),
        "mascot_avatar.png": (512, 512),
        "app_icon_1024.png": (1024, 1024),
        "app_icon_512.png": (512, 512),
        "app_icon_256.png": (256, 256),
        "app_icon_128.png": (128, 128),
        "app_icon_64.png": (64, 64),
        "app_icon_32.png": (32, 32),
        "app_icon_16.png": (16, 16),
    }
    for filename, (expected_w, expected_h) in required_pngs.items():
        file_path = BRAND_DIR / filename
        assert file_path.exists(), f"Asset {filename} does not exist at {file_path}"
        with Image.open(file_path) as img:
            assert img.size == (expected_w, expected_h), f"{filename} size {img.size} != {(expected_w, expected_h)}"
            assert img.mode in ("RGBA", "RGB")
            
    assert (BRAND_DIR / "app_icon.icns").exists(), "app_icon.icns does not exist"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_brand_assets.py -v`
Expected: FAIL with "Asset mascot_hero.png does not exist"

- [ ] **Step 3: Implement asset generation and multi-resolution downsampling pipeline**

1. 生成 3D 盲盒小柴犬立绘与 Squircle 图标母版；
2. 编写 `scripts/generate_brand_assets.py`，实现 `process_and_generate_assets()`，使用 `PIL.Image.Resampling.LANCZOS` 导出 512/256/128/64/32/16 PNG，并调用 `iconutil` 打包为 `app_icon.icns`。
3. 执行生成脚本填充 `resource/assets/brand/`。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_brand_assets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add resource/assets/brand/ scripts/generate_brand_assets.py tests/test_brand_assets.py
git commit -m "feat(brand): generate mascot and multi-resolution app icon assets"
```

---

### Task 2: 统一品牌资产提供者 (`BrandAssets`) 与单元测试

**Files:**
- Modify: `apps/atbmind_desktop/theme.py`
- Modify: `tests/test_brand_assets.py`

**Interfaces:**
- Consumes: `resource/assets/brand/` 文件路径
- Produces: `BrandAssets.get_brand_dir()`, `BrandAssets.get_app_icon()`, `BrandAssets.get_mascot_avatar(size)`, `BrandAssets.get_mascot_hero()`

- [ ] **Step 1: Write the failing tests for `BrandAssets` provider**

```python
# tests/test_brand_assets.py 追加测试
from apps.atbmind_desktop.theme import BrandAssets
from PySide6.QtGui import QIcon, QPixmap

def test_brand_assets_provider_methods():
    icon = BrandAssets.get_app_icon()
    assert isinstance(icon, QIcon)
    assert not icon.isNull()
    
    avatar = BrandAssets.get_mascot_avatar(24)
    assert isinstance(avatar, QPixmap)
    assert not avatar.isNull()
    assert avatar.width() == 24
    assert avatar.height() == 24
    
    hero = BrandAssets.get_mascot_hero()
    assert isinstance(hero, QPixmap)
    assert not hero.isNull()

def test_brand_assets_fallback_when_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(BrandAssets, "get_brand_dir", lambda: tmp_path / "non_existent")
    # 验证降级情况下不抛异常且返回可用 QIcon/QPixmap
    fallback_icon = BrandAssets.get_app_icon()
    assert isinstance(fallback_icon, QIcon)
    fallback_avatar = BrandAssets.get_mascot_avatar(24)
    assert isinstance(fallback_avatar, QPixmap)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_brand_assets.py::test_brand_assets_provider_methods -v`
Expected: FAIL with "ImportError: cannot import name 'BrandAssets' from 'apps.atbmind_desktop.theme'"

- [ ] **Step 3: Implement `BrandAssets` in `apps/atbmind_desktop/theme.py`**

实现 `BrandAssets` 类：
- `get_brand_dir() -> Path`：定位 `resource/assets/brand`。
- `get_app_icon() -> QIcon`：聚合全尺寸 PNG，带内存缓存与回退降级。
- `get_mascot_avatar(size: int = 24) -> QPixmap`：支持圆角或透明裁切，带尺寸缓存。
- `get_mascot_hero() -> QPixmap`：返回完整立绘。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_brand_assets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/theme.py tests/test_brand_assets.py
git commit -m "feat(desktop): implement BrandAssets provider with caching and fallback"
```

---

### Task 3: 桌面主程序与主窗口图标集成

**Files:**
- Modify: `apps/atbmind_desktop/main.py`
- Modify: `apps/atbmind_desktop/main_window.py`

**Interfaces:**
- Consumes: `BrandAssets.get_app_icon()`
- Produces: 全局 `QApplication` 与 `ATBMindMainWindow` 的 windowIcon 绑定。

- [ ] **Step 1: Write test for window icon binding**

在 `tests/test_main_window.py` 或新建测试中验证 `ATBMindMainWindow` 设置了有效 windowIcon。

```python
from apps.atbmind_desktop.main_window import ATBMindMainWindow
from apps.atbmind_desktop.main import create_app

def test_main_window_has_brand_icon():
    app = create_app(["--headless"])
    assert not app.windowIcon().isNull()
    win = ATBMindMainWindow()
    assert not win.windowIcon().isNull()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_brand_assets.py::test_main_window_has_brand_icon -v`
Expected: FAIL (app.windowIcon() is null)

- [ ] **Step 3: Integrate `BrandAssets.get_app_icon()` in `main.py` and `main_window.py`**

- `main.py:create_app()`: `app.setWindowIcon(BrandAssets.get_app_icon())`
- `main_window.py:ATBMindMainWindow.__init__()`: `self.setWindowIcon(BrandAssets.get_app_icon())`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_brand_assets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/main.py apps/atbmind_desktop/main_window.py tests/test_brand_assets.py
git commit -m "feat(desktop): set application and main window icon with BrandAssets"
```

---

### Task 4: 导航侧边栏 (`NavigationSidebar`) 品牌展示区域集成

**Files:**
- Modify: `apps/atbmind_desktop/widgets/navigation_sidebar.py`
- Modify: `tests/test_navigation_sidebar.py`

**Interfaces:**
- Consumes: `BrandAssets.get_mascot_avatar(size=26)`
- Produces: 侧边栏顶部的品牌展示组件 `BrandHeaderWidget`

- [ ] **Step 1: Write test for brand header widget in navigation sidebar**

```python
from apps.atbmind_desktop.widgets.navigation_sidebar import NavigationSidebar

def test_navigation_sidebar_brand_header_presence():
    sidebar = NavigationSidebar()
    assert hasattr(sidebar, "brand_header")
    assert sidebar.brand_header.isVisible()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_navigation_sidebar.py -k brand_header -v`
Expected: FAIL (sidebar has no attribute 'brand_header')

- [ ] **Step 3: Implement `BrandHeaderWidget` in `NavigationSidebar`**

在侧边栏顶部窗口控制区与会话区之间，添加展示 26×26 柴犬盲盒头像与 "ATBMind" 字体 Logo 的组件，在折叠状态下自适应隐藏文本只留小头像。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_navigation_sidebar.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/widgets/navigation_sidebar.py tests/test_navigation_sidebar.py
git commit -m "feat(ui): add brand mascot header to NavigationSidebar"
```

---

### Task 5: 设置对话框关于卡片与 README 文档资产替换

**Files:**
- Modify: `apps/atbmind_desktop/widgets/settings_dialog.py`
- Modify: `README.md`
- Modify: `tests/test_settings_dialog.py`

**Interfaces:**
- Consumes: `BrandAssets.get_mascot_hero()`, `resource/assets/brand/app_icon_128.png`
- Produces: 设置关于对话框中的代言人展示卡片，以及 README 的全新品牌 Logo。

- [ ] **Step 1: Write test for settings dialog about card**

```python
from apps.atbmind_desktop.widgets.settings_dialog import SettingsDialog

def test_settings_dialog_contains_mascot_card():
    dlg = SettingsDialog()
    assert hasattr(dlg, "about_card") or hasattr(dlg, "mascot_label")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_settings_dialog.py -k mascot -v`
Expected: FAIL

- [ ] **Step 3: Update `SettingsDialog` and `README.md`**

1. 在 `SettingsDialog` 中增加关于代言人的卡片与展示区域；
2. 更新根目录 `README.md` 顶部的 Logo 链接指向 `resource/assets/brand/app_icon_128.png` 并标注全新吉祥物。

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_settings_dialog.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/atbmind_desktop/widgets/settings_dialog.py README.md tests/test_settings_dialog.py
git commit -m "docs & ui: integrate mascot about card in settings and update README banner"
```

---

### Task 6: 全工程回归验证与发布准备

**Files:**
- None (全量测试与验证)

- [ ] **Step 1: Run full automated pytest test suite**

Run: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
Expected: 180+ passed, 0 failed

- [ ] **Step 2: Verification of GUI assets resolution and packaging**

Run: `python scripts/generate_brand_assets.py --verify`
Expected: All icons verified clean.
