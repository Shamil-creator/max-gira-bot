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


def test_main_imports_act_ku_cron():
    content = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "get_act_ku_payment_every_month" in content
    assert "monthly_act_ku_msg_" in content


def test_act_ku_sort_key_groups_with_ku_documents():
    from datetime import date as _date
    from handlers.admin_group import admin_my_bills_sort_key
    doc = {"file_name": "Акт №5 КУ март 2026.xlsx", "date_added": _date(2026, 3, 29)}
    cat, _ = admin_my_bills_sort_key(doc)
    assert cat == 1, "Акт КУ with numbered format should sort into category 1"


def test_sendall_command_exists_with_access_check():
    content = (ROOT / "handlers" / "admin_group.py").read_text(encoding="utf-8")
    assert 'Command("sendall")' in content, "/sendall command handler missing"
    assert "has_admin_access" in content, "admin access check missing"


def test_build_functions_have_no_db_writes():
    content = (ROOT / "handlers" / "check_payment_status.py").read_text(encoding="utf-8")
    import re
    for func_name in ("build_rent_invoice", "build_rent_act", "build_ku_act_payment"):
        m = re.search(rf"async def {func_name}\(.*?\n(?=async def |\Z)", content, re.DOTALL)
        assert m, f"{func_name} not found"
        body = m.group(0)
        assert "new_data_insert" not in body, f"{func_name} must not write to DB"
        assert "UPDATE" not in body, f"{func_name} must not contain UPDATE"
        assert "INSERT" not in body, f"{func_name} must not contain INSERT"
