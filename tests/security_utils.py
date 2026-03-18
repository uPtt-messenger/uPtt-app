# 測試用的安全性工具

class PasswordLeakError(Exception):
    """當偵測到密碼可能洩漏時拋出的例外"""
    pass

# 定義一個特殊的測試密碼金雀鳥 (Canary)
TEST_PASSWORD_CANARY = "SECRET_CANARY_PW_12345"
