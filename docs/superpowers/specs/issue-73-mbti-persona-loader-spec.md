# Specification: Issue #73 - MBTI Persona System & PersonaLoader

## 1. Overview & Context
- **Issue**: [#73](https://github.com/aitobox/ATBMind/issues/73)
- **Parent Epic**: [#69](https://github.com/aitobox/ATBMind/issues/69) (Octop Architecture Adoption Phase 2)
- **Step**: Step 4 of 4 (Final step of Epic #69)
- **Objective**: Establish a complete 16 MBTI personality profile dataset and 6-dimensional behavioral guideline matrix, and implement `PersonaLoader` to inject structured psychological personas into `RobotRole` system prompts.

## 2. Architecture & Design Details

### 2.1 Persona Schema (`atbmind_core/roles/persona.py`)
- `MBTIBehaviorMapping`: 6 interaction dimensions:
  - `answer_style`: concise/rigorous vs expressive/warm
  - `casual_chat`: focused/guiding vs sociable/humorous
  - `conflict_resolution`: logic-driven vs empathy-mediated
  - `creativity`: architectural/systemic vs divergent/exploratory
  - `emotion`: analytical/composed vs compassionate/supportive
  - `planning`: structured/milestone-driven vs flexible/adaptive
- `MBTIDimensions`: EI, SN, TF, JP
- `MBTIProfile`: code, name, archetype, description, dimensions, behaviors
- Complete dataset of all 16 MBTI profiles:
  - INTJ, INTP, ENTJ, ENTP
  - INFJ, INFP, ENFJ, ENFP
  - ISTJ, ISFJ, ESTJ, ESFJ
  - ISTP, ISFP, ESTP, ESFP
- `PersonaLoader.render_soul(role: RobotRole, mbti_code: Optional[str] = None) -> str`

### 2.2 Integration with `RobotRole` (`atbmind_core/roles/schema.py`)
- Add `mbti: Optional[str] = Field(default=None, description="MBTI profile code, e.g. 'INTJ'")`
- Define alias `RoleDefinition = RobotRole`
- In `RobotRole.build_system_prompt()`: include rendered MBTI persona block if `self.mbti` is present.

## 3. Implementation Task List
- [x] Task 1: Module design & contract definitions (`atbmind_core/roles/persona.py`)
- [x] Task 2: Unit tests & TDD test cases (`tests/test_mbti_persona.py`)
- [x] Task 3: Core logic implementation (`persona.py`, `schema.py`, `loader.py`)
- [x] Task 4: Integration verification & test suite pass (100% pytest pass across all tests)
- [x] Task 5: grill-me audit & stress-testing (all 16 MBTI profiles complete, prompt rendering, role definition injection)

## 4. Verification Plan
- `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/test_mbti_persona.py -v`
- Full regression suite: `PYTHONPATH=src conda run -n ATBMind python -m pytest tests/`
