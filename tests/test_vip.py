import hashlib

from src.uPtt import vip


def test_non_whitelisted_account_is_not_vip():
    assert vip.is_vip_account("SomeRandomUser") is False


def test_empty_or_none_id_is_not_vip():
    assert vip.is_vip_account("") is False
    assert vip.is_vip_account(None) is False


def test_whitelisted_hash_is_case_insensitive(monkeypatch):
    digest = hashlib.sha256("viptester".encode("utf-8")).hexdigest()
    monkeypatch.setattr(vip, "_VIP_ID_HASHES", {digest})

    assert vip.is_vip_account("VipTester") is True
    assert vip.is_vip_account("VIPTESTER") is True
    assert vip.is_vip_account("viptester") is True
    assert vip.is_vip_account("nottester") is False
