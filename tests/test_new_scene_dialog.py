"""Tests for the new scene dialog pure-logic helpers."""

import pytest

from tnh_scene_compiler.new_scene_dialog import build_scene_text, _slugify


# -- _slugify ----------------------------------------------------------------

class TestSlugify:
    def test_simple(self):
        assert _slugify("A Morning Chat") == "a_morning_chat"

    def test_special_chars(self):
        assert _slugify("Jean's Room!") == "jean_s_room"

    def test_empty(self):
        assert _slugify("") == ""

    def test_leading_trailing_spaces(self):
        assert _slugify("  hello world  ") == "hello_world"

    def test_consecutive_specials(self):
        assert _slugify("a--b??c") == "a_b_c"


# -- build_scene_text --------------------------------------------------------

class TestBuildSceneTextEmpty:
    def test_basic_cinematic(self):
        text = build_scene_text(
            title="Morning Chat",
            scene_id="mymod_morning_chat",
            character="JeanGrey",
            scene_type="cinematic",
            trigger="manual",
        )
        assert "Title: Morning Chat" in text
        assert "Scene Id: mymod_morning_chat" in text
        assert "Character: JeanGrey" in text
        assert "Scene Type: cinematic" in text
        assert "Trigger: manual" in text

    def test_empty_body(self):
        text = build_scene_text(
            title="Test",
            scene_id="mod_test",
            character="JeanGrey",
            example="empty",
        )
        lines = text.strip().split("\n")
        body_lines = [l for l in lines if not l.startswith(("Title:", "Scene Id:", "Character:", "Scene Type:", "Trigger:"))]
        assert all(l.strip() == "" for l in body_lines)

    def test_phone_no_trigger(self):
        text = build_scene_text(
            title="Phone Call",
            scene_id="mod_phone",
            character="JeanGrey",
            scene_type="phone",
        )
        assert "Trigger:" not in text
        assert "Scene Type: phone" in text

    def test_texting_no_trigger(self):
        text = build_scene_text(
            title="Text",
            scene_id="mod_text",
            character="JeanGrey",
            scene_type="texting",
        )
        assert "Trigger:" not in text
        assert "Openness:" not in text

    def test_location_included(self):
        text = build_scene_text(
            title="T",
            scene_id="mod_t",
            character="JeanGrey",
            location="KITCHEN",
        )
        assert "Location: KITCHEN" in text

    def test_description_included(self):
        text = build_scene_text(
            title="T",
            scene_id="mod_t",
            character="JeanGrey",
            description="A short scene.",
        )
        assert "Description: A short scene." in text


class TestBuildSceneTextDialogue:
    def test_featured_has_show(self):
        text = build_scene_text(
            title="Chat",
            scene_id="mod_chat",
            character="JeanGrey",
            location="KITCHEN",
            example="dialogue",
            featured=True,
        )
        assert "INT. KITCHEN" in text
        assert "[[show JeanGrey]]" in text
        assert "JEANGREY" in text
        assert "PLAYER" in text

    def test_non_featured_no_show(self):
        text = build_scene_text(
            title="Chat",
            scene_id="mod_chat",
            character="SomeNPC",
            example="dialogue",
            featured=False,
        )
        assert "[[show" not in text
        assert "SOMENPC" in text

    def test_phone_has_phone_open_close(self):
        text = build_scene_text(
            title="Chat",
            scene_id="mod_chat",
            character="JeanGrey",
            scene_type="phone",
            example="dialogue",
        )
        assert "[[phone open JeanGrey]]" in text
        assert "[[phone close]]" in text
        assert "INT." not in text
        assert "[[show" not in text

    def test_texting_has_phone_open_close(self):
        text = build_scene_text(
            title="Chat",
            scene_id="mod_chat",
            character="JeanGrey",
            scene_type="texting",
            example="dialogue",
        )
        assert "[[phone open JeanGrey]]" in text
        assert "[[phone close]]" in text

    def test_fallback_location(self):
        text = build_scene_text(
            title="Chat",
            scene_id="mod_chat",
            character="JeanGrey",
            example="dialogue",
        )
        assert "INT. LOCATION" in text


class TestBuildSceneTextChoices:
    def test_featured_has_show(self):
        text = build_scene_text(
            title="Choice",
            scene_id="mod_choice",
            character="JeanGrey",
            example="choices",
            featured=True,
        )
        assert "[[show JeanGrey]]" in text
        assert "[[choice]]" in text
        assert "[[/choice]]" in text

    def test_non_featured_no_show(self):
        text = build_scene_text(
            title="Choice",
            scene_id="mod_choice",
            character="SomeNPC",
            example="choices",
            featured=False,
        )
        assert "[[show" not in text
        assert "[[choice]]" in text

    def test_phone_has_phone_open_close(self):
        text = build_scene_text(
            title="Choice",
            scene_id="mod_choice",
            character="JeanGrey",
            scene_type="phone",
            example="choices",
        )
        assert "[[phone open JeanGrey]]" in text
        assert "[[phone close]]" in text
        assert "[[choice]]" in text
        assert "[[/choice]]" in text


class TestBuildSceneTextConditional:
    def test_featured_has_show(self):
        text = build_scene_text(
            title="Cond",
            scene_id="mod_cond",
            character="JeanGrey",
            example="conditional",
            featured=True,
        )
        assert "[[show JeanGrey]]" in text
        assert "[[if JeanGrey.love >= 500]]" in text
        assert "[[else]]" in text
        assert "[[/if]]" in text

    def test_non_featured_no_show(self):
        text = build_scene_text(
            title="Cond",
            scene_id="mod_cond",
            character="SomeNPC",
            example="conditional",
            featured=False,
        )
        assert "[[show" not in text
        assert "[[if SomeNPC.love >= 500]]" in text

    def test_phone_has_phone_open_close(self):
        text = build_scene_text(
            title="Cond",
            scene_id="mod_cond",
            character="JeanGrey",
            scene_type="phone",
            example="conditional",
        )
        assert "[[phone open JeanGrey]]" in text
        assert "[[phone close]]" in text
        assert "[[if JeanGrey.love >= 500]]" in text

    def test_fallback_character(self):
        text = build_scene_text(
            title="Cond",
            scene_id="mod_cond",
            character="",
            example="conditional",
        )
        assert "[[if Character.love >= 500]]" in text
