"""Cổng mở rộng phía máy chủ (server plugins).

Mỗi tệp Python trong thư mục này (không bắt đầu bằng '_') có hàm
    register(app, ctx)
sẽ được nạp tự động khi khởi động. `ctx` cung cấp các tiện ích dùng chung:
    ctx.q, ctx.ex          — truy vấn SQLite
    ctx.require(perm)      — decorator phân quyền (S0/S1/CW)
    ctx.get_setting, ctx.set_setting
    ctx.fire_webhook(event, payload)
Xem docs/MODULES.md để biết quy ước đặt route (/api/modules/<key>/...).
"""
import importlib
import os
import traceback
from types import SimpleNamespace

LOADED = []


def load_plugins(app):
    import db
    import auth
    from app import fire_webhook
    ctx = SimpleNamespace(q=db.q, ex=db.ex, get_setting=db.get_setting, set_setting=db.set_setting,
                          require=auth.require, audit=auth.audit, fire_webhook=fire_webhook)
    here = os.path.dirname(os.path.abspath(__file__))
    for fn in sorted(os.listdir(here)):
        if not fn.endswith(".py") or fn.startswith("_"):
            continue
        name = fn[:-3]
        try:
            mod = importlib.import_module(f"modules.{name}")
            if hasattr(mod, "register"):
                mod.register(app, ctx)
                LOADED.append(name)
                print(f"  + module máy chủ: {name}")
        except Exception:
            print(f"  ! lỗi nạp module {name}")
            traceback.print_exc()
