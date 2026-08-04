# --- VIP 帳號判定 ---
#
# app 是純 client、沒有自己的後端可以核發資格，因此採用最輕量的作法：
# 白名單存 sha256(ptt_id.lower()) 的 hex digest，不在原始碼中留下明文 ID。
# 這不是防篡改機制（本地 code 本來就能被改），只是不讓帳號一眼被看到。

import hashlib

_VIP_ID_HASHES = {
    # sha256(ptt_id.lower())
}


def is_vip_account(ptt_id: str) -> bool:
    """回傳指定 PTT ID 是否為 VIP 帳號（大小寫不敏感）。"""
    if not ptt_id:
        return False
    digest = hashlib.sha256(ptt_id.strip().lower().encode("utf-8")).hexdigest()
    return digest in _VIP_ID_HASHES
