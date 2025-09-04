# Setting the environment variable for the current session
import os
os.environ["DJANGO_SETTINGS_MODULE"] = "pharma_web.settings"

import django, importlib, traceback, sys
try:
    django.setup()
    importlib.import_module("core.views")
    print("✅ core.views imported successfully")
except Exception:
    traceback.print_exc()
    sys.exit(1)