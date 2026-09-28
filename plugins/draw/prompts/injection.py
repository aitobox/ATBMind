"""
ATBMind-Draw Domain Prompt Injection
Provides latent intent rules, common-sense parameter defaults, and anti-distortion constraints for portrait retouching.
"""

DRAW_DOMAIN_PROMPT_INJECTION = """
[ATBMind-Draw 图像精修领域潜需求与隐式约束规范]
1. 形体塑形联动保护 (Body Shaping & Anti-Distortion):
   - 当用户表达瘦身、显瘦、瘦腰、拉长腿、直角肩等形体微调意图时，必须自动开启服装边缘防畸变保护 (`clothing_protection=True`, `preserve_ratio=0.85`) 以及背景网格防拉扯锁定 (`background_lock=True`)。
   - 默认形变强度 `intensity` 应控制在自然真实范围 (`0.12` ~ `0.18`)，除非用户明确要求强烈效果，严禁超过 `0.35` 导致背景砖墙或门框弯曲。

2. 面部重塑与结构协调 (Facial Reshaping & Harmony):
   - 瘦脸、下颌线收紧或发际线调整时，必须自动联动颈部连接处平滑过渡 (`neck_transition_smooth=True`)，并保持双侧光影对称。

3. 肤质精修与质感保留 (Skin Retouching & Texture Preservation):
   - 磨皮、祛痘、提亮肤色、去黑眼圈或去油光时，默认启用双频保留原生皮肤微纹理 (`preserve_skin_texture=True`) 与五官高光/眼神光保护 (`protect_catchlights=True`)，避免塑料假面感。

4. 光影与色彩统一 (Lighting & Color Consistency):
   - 局部提亮或追光补光时，默认保持色温与环境光匹配 (`ambient_color_match=True`)。
""".strip()


def get_draw_domain_prompt_injection() -> str:
    """Returns the domain-specific latent intent prompt rules for ATBMind-Draw."""
    return DRAW_DOMAIN_PROMPT_INJECTION
