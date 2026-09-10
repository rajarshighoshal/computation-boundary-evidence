"""Small experiment settings; Docker supplies the isolation boundary."""
from __future__ import annotations

import json


def codex_config(model: str, effort: str) -> str:
    return f'''model = {json.dumps(model)}
model_reasoning_effort = {json.dumps(effort)}
forced_login_method = "chatgpt"
web_search = "disabled"
check_for_update_on_startup = false
history.persistence = "none"
'''
