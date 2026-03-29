# from .allocate_resources import *
# from .potential_review import *
# from .update_details import action_update_resource_data
# from .upload_data import *
# from .allocate_demands import *
# from .add_details import *
# from .unassign_resources import *



import importlib
import pkgutil
import os

def _auto_register_actions():
    package_name = __name__  # 'actions'
    package_path = os.path.dirname(__file__)

    for _, module_name, _ in pkgutil.iter_modules([package_path]):
        # Skip private modules and known non-action ones
        if module_name.startswith("_") or module_name in {"context", "utils"}:
            continue

        full_module_name = f"{package_name}.{module_name}"
        if "upload_data" in full_module_name:
            continue
        try:
            importlib.import_module(full_module_name)
            # print(f"[Auto-registered actions from] {full_module_name}")
        except Exception as e:
            print(f"[Auto-register failed] {full_module_name}: {e}")

# Auto-run when the package is imported
_auto_register_actions()