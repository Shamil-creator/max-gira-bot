from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from handlers.admin_chat import format_admin_text


def test_admin_prefixes():
    assert format_admin_text("payment", "ok").startswith("[ОПЛАТА]")
    assert format_admin_text("tech", "ok").startswith("[ТЕХЗАЯВКА]")
    assert format_admin_text("repair", "ok").startswith("[РЕМОНТ]")
    assert format_admin_text("docs", "ok").startswith("[ДОКУМЕНТЫ]")
    assert format_admin_text("admin", "ok").startswith("[АДМИН]")


def test_no_message_thread_id_left_in_handlers():
    handlers_dir = ROOT / "handlers"
    for path in handlers_dir.glob("*.py"):
        content = path.read_text(encoding="utf-8")
        assert "message_thread_id" not in content, f"message_thread_id found in {path.name}"


def test_no_external_redis_dependency():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "redis" not in requirements


def test_main_has_stable_self_alias_for_main_imports():
    content = (ROOT / "main.py").read_text(encoding="utf-8")
    assert 'sys.modules.setdefault("main", sys.modules[__name__])' in content
