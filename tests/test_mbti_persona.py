"""Unit tests for 16 MBTI structured persona profiles and PersonaLoader (Issue #73)."""

from __future__ import annotations

import pytest

from atbmind_core.roles.persona import (
    ALL_MBTI_CODES,
    MBTI_PROFILES,
    MBTIProfile,
    PersonaLoader,
    get_mbti_profile,
)
from atbmind_core.roles.schema import RobotRole, RoleDefinition


def test_all_16_mbti_profiles_exist_and_complete():
    expected_codes = {
        "INTJ", "INTP", "ENTJ", "ENTP",
        "INFJ", "INFP", "ENFJ", "ENFP",
        "ISTJ", "ISFJ", "ESTJ", "ESFJ",
        "ISTP", "ISFP", "ESTP", "ESFP",
    }
    assert set(ALL_MBTI_CODES) == expected_codes
    assert set(MBTI_PROFILES.keys()) == expected_codes

    for code in expected_codes:
        profile = get_mbti_profile(code)
        assert profile is not None
        assert isinstance(profile, MBTIProfile)
        assert profile.code == code
        assert bool(profile.name)
        assert bool(profile.archetype)
        assert bool(profile.description)

        # Check 4 axes
        assert profile.dimensions.ei in ("E", "I")
        assert profile.dimensions.sn in ("S", "N")
        assert profile.dimensions.tf in ("T", "F")
        assert profile.dimensions.jp in ("J", "P")

        # Check 6 behavior dimensions
        assert bool(profile.behaviors.answer_style)
        assert bool(profile.behaviors.casual_chat)
        assert bool(profile.behaviors.conflict_resolution)
        assert bool(profile.behaviors.creativity)
        assert bool(profile.behaviors.emotion)
        assert bool(profile.behaviors.planning)


def test_persona_loader_render_soul():
    profile = get_mbti_profile("INTJ")
    assert profile is not None

    soul_md = PersonaLoader.render_soul(role=None, mbti_code="INTJ")
    assert "INTJ" in soul_md
    assert "回答风格" in soul_md or "Answer Style" in soul_md
    assert "规划条理" in soul_md or "Planning" in soul_md
    assert profile.name in soul_md


def test_robot_role_system_prompt_with_mbti():
    role = RobotRole(
        role_id="coder",
        name="代码专家",
        system_prompt="你是一名资深架构师与代码开发专家。",
        mbti="INTJ",
    )

    full_prompt = role.build_system_prompt()
    assert "你是一名资深架构师与代码开发专家。" in full_prompt
    assert "INTJ" in full_prompt
    assert "MBTI" in full_prompt


def test_role_definition_alias_compatibility():
    assert RoleDefinition is RobotRole
    role_def = RoleDefinition(role_id="analyst", name="数据分析师", mbti="INTP")
    assert role_def.mbti == "INTP"
    assert "INTP" in role_def.build_system_prompt()
