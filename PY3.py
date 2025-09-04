import os
os.environ["DJANGO_SETTINGS_MODULE"] = "pharma_web.settings"
import django, importlib, traceback, sys, os
try:
    django.setup()
    m = importlib.import_module("core.views")
    print("Imported core.views OK")
    print("Names in module core.views:")
    print(sorted([n for n in dir(m) if not n.startswith("_")]))
except Exception:
    traceback.print_exc()
    sys.exit(1)
