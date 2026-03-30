import pytest
from clawdia.pc.knowledge import KnowledgeBase


@pytest.fixture
def kb_path(tmp_path):
    return tmp_path / "knowledge.yaml"


@pytest.fixture
def kb(kb_path):
    return KnowledgeBase(kb_path)


def test_load_empty(kb):
    assert kb.to_prompt_context() == ""


def test_load_existing(kb_path):
    kb_path.write_text(
        "pc:\n  browser: firefox\nservices:\n  emby:\n    url: http://emby:8096\n"
    )
    kb = KnowledgeBase(kb_path)
    context = kb.to_prompt_context()
    assert "firefox" in context
    assert "emby" in context
    assert "http://emby:8096" in context


def test_update_section(kb, kb_path):
    kb.update("pc", "browser", "firefox")
    kb2 = KnowledgeBase(kb_path)
    assert kb2.data["pc"]["browser"] == "firefox"


def test_update_nested_section(kb, kb_path):
    kb.update("services", "emby", {"url": "http://emby:8096", "username": "vossi"})
    kb2 = KnowledgeBase(kb_path)
    assert kb2.data["services"]["emby"]["url"] == "http://emby:8096"


def test_add_preference(kb, kb_path):
    kb.add_preference("use keyboard shortcuts when possible")
    kb2 = KnowledgeBase(kb_path)
    assert "use keyboard shortcuts when possible" in kb2.data["preferences"]


def test_add_correction(kb, kb_path):
    kb.add_correction("open emby", "emby is at http://emby:8096, not emby.media")
    kb2 = KnowledgeBase(kb_path)
    assert len(kb2.data["corrections"]) == 1
    assert kb2.data["corrections"][0]["trigger"] == "open emby"
    assert "emby:8096" in kb2.data["corrections"][0]["learned"]


def test_to_prompt_context_formatted(kb):
    kb.update("pc", "browser", "firefox")
    kb.update("services", "emby", {"url": "http://emby:8096"})
    kb.add_preference("fullscreen browser after opening")
    kb.add_correction("open emby", "use local URL not emby.media")
    context = kb.to_prompt_context()
    assert "browser: firefox" in context
    assert "emby" in context
    assert "fullscreen" in context
    assert "use local URL" in context
