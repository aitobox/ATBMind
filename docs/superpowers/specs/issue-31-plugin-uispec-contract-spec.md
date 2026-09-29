# Issue #31 Specification: PluginUISpec Contract & ATBDraw `get_ui_spec()`

## 1. Objective
Establish the standard UI specification contract (`PluginUISpec`) for ATBMind plugins and implement `DrawPlugin.get_ui_spec()` to expose ATBDraw's models, aspect ratios, Doubao-style art styles, and portrait retouching templates to the host desktop UI (`FooterDock` and `StylePopover`).

## 2. Data Model (`atbmind_core/plugins/schemas.py`)
Define `PluginUISpec(BaseModel)`:
- `plugin_id: str`: Unique plugin identifier (e.g. `"draw"`).
- `display_name: str`: Human-readable plugin name (e.g. `"图像生成 (ATBDraw)"`).
- `icon: str`: UI icon string/emoji (e.g. `"🖼️"`).
- `supports_attachments: bool = True`: Whether the plugin accepts file attachments.
- `attachment_types: List[str] = Field(default_factory=lambda: [".png", ".jpg", ".jpeg", ".webp"])`: Allowed attachment file extensions.
- `models: List[str] = Field(default_factory=list)`: Supported generation/retouching models.
- `aspect_ratios: List[str] = Field(default_factory=list)`: Supported output aspect ratios.
- `styles: List[Dict[str, str]] = Field(default_factory=list)`: Art style descriptors (`id`, `name`, `icon`, `prompt_suffix`).
- `templates: List[TemplateMetadata] = Field(default_factory=list)`: Domain templates available for selection in the UI.

## 3. Base Plugin SPI (`atbmind_core/plugins/base.py`)
Extend `ATBMindPlugin` with a non-abstract method:
```python
def get_ui_spec(self) -> Optional[PluginUISpec]:
    """
    Returns the UI specification for host UI controls (FooterDock, StylePopover),
    or None if the plugin operates headless without dedicated UI controls.
    """
    return None
```

## 4. `DrawPlugin.get_ui_spec()` (`plugins/draw/plugin.py`)
Return a populated `PluginUISpec` instance with:
- `plugin_id`: `"draw"`
- `display_name`: `"图像生成 (ATBDraw)"`
- `icon`: `"🖼️"`
- `supports_attachments`: `True`
- `attachment_types`: `[".png", ".jpg", ".jpeg", ".webp"]`
- `models`: `["Seedream 4.5", "Flux.1", "SDXL", "Mock Adapter"]`
- `aspect_ratios`: `["自动", "1:1", "16:9", "9:16", "3:4"]`
- `styles`: Doubao-style art styles list (`人像摄影`, `电影写真`, `中国风`, `动漫`, `3D渲染`, `赛博朋克`, `水墨画`, `油画`, `古典`, `水彩画`), each with `id`, `name`, `icon`, and `prompt_suffix`.
- `templates`: `self.get_templates()`
