import importlib, traceback
try:
    importlib.import_module("core.views")
    print("OK")
except Exception:
    traceback.print_exc()
