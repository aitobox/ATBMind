# Implementation Plan - Issue #73: MBTI Persona System & PersonaLoader

## Overview
Implement the full 16 MBTI personality profile dataset and 6-dimensional behavioral guideline matrix, and integrate `PersonaLoader` with `RobotRole` / `RoleDefinition` schema to inject structured personas into role system prompts.

## Proposed Changes

### 1. `atbmind_core/roles/persona.py`
- Define data structures:
  - `MBTIBehaviorMapping`
  - `MBTIDimensions`
  - `MBTIProfile`
- Implement complete dataset containing all 16 MBTI profiles:
  - Analysts: `INTJ`, `INTP`, `ENTJ`, `ENTP`
  - Diplomats: `INFJ`, `INFP`, `ENFJ`, `ENFP`
  - Sentinels: `ISTJ`, `ISFJ`, `ESTJ`, `ESFJ`
  - Explorers: `ISTP`, `ISFP`, `ESTP`, `ESFP`
- Implement `get_mbti_profile(code: str) -> Optional[MBTIProfile]`
- Implement `PersonaLoader`:
  - `get_profile(code: str) -> Optional[MBTIProfile]`
  - `render_soul(role: Any, mbti_code: Optional[str] = None) -> str`

### 2. `atbmind_core/roles/schema.py`
- Add `mbti: Optional[str] = Field(default=None, description="MBTI profile code, e.g. 'INTJ'")` to `RobotRole`.
- Add alias `RoleDefinition = RobotRole`.
- In `RobotRole.build_system_prompt()`, inject rendered MBTI soul block when `self.mbti` is present.

### 3. `atbmind_core/roles/__init__.py`
- Export `MBTIProfile`, `MBTIBehaviorMapping`, `PersonaLoader`, `get_mbti_profile`, `RoleDefinition`.

### 4. `tests/test_mbti_persona.py`
- Unit tests:
  - `test_all_16_mbti_profiles_exist_and_complete`
  - `test_mbti_profile_dimensions_and_behaviors`
  - `test_persona_loader_render_soul`
  - `test_robot_role_system_prompt_with_mbti`
  - `test_role_definition_alias_compatibility`

## Verification
- `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_mbti_persona.py -v`
- Full regression suite: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
