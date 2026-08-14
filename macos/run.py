"""Development and packaged entry point for SuperMenu on macOS."""

from __future__ import annotations

import json
import os
import re
import sys


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


def run_packaged_smoke_test():
    from src.config.build_info import APP_VERSION, BUILD_CHANNEL
    from supermenu_core.config.openai_models import (
        AVAILABLE_MODELS,
        DEFAULT_OPENAI_MODEL,
    )
    from src.utils.paths import packaged_resource_status
    from src.utils.permissions import current_permission_status

    status = packaged_resource_status()
    status["models"] = AVAILABLE_MODELS
    status["default_model"] = DEFAULT_OPENAI_MODEL
    status["app_version"] = APP_VERSION
    status["build_channel"] = BUILD_CHANNEL
    status["model_config_ok"] = (
        DEFAULT_OPENAI_MODEL in AVAILABLE_MODELS and bool(AVAILABLE_MODELS)
    )
    status["build_config_ok"] = BUILD_CHANNEL in {"stable", "beta"} and (
        APP_VERSION == "dev"
        or re.fullmatch(
            r"\d+\.\d+\.\d+(?:-(?:beta|rc)\.\d+)?",
            APP_VERSION,
        )
        is not None
    )
    permission_status = current_permission_status()
    status["permission_checks"] = {
        "accessibility": permission_status.accessibility_check_available,
    }
    status["permission_checks_ok"] = sys.platform != "darwin" or all(
        status["permission_checks"].values()
    )
    status["ok"] = bool(
        status["ok"]
        and status["model_config_ok"]
        and status["build_config_ok"]
        and status["permission_checks_ok"]
    )
    print(json.dumps(status, ensure_ascii=False))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        sys.exit(run_packaged_smoke_test())
    from src.main import SuperMenu

    application = SuperMenu()
    sys.exit(application.run())
