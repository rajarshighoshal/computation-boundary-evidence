"""Generate the same isolated native Codex configuration for both conditions."""
from __future__ import annotations

import json
from pathlib import PurePosixPath


def codex_config(root: str, scratch: str, control: str, profile: str,
                 model: str, effort: str) -> str:
    if profile not in {"extract", "repair"}:
        raise ValueError("Invalid native permission profile")
    for path in (root, scratch, control):
        if not PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise ValueError("Runtime paths must be explicit absolute paths")
    # TOML basic strings use JSON-compatible escaping for these controlled paths.
    q = json.dumps
    return f'''model = {q(model)}
model_reasoning_effort = {q(effort)}
default_permissions = {q(profile)}
approval_policy = "never"
web_search = "disabled"
forced_login_method = "chatgpt"
check_for_update_on_startup = false
allow_login_shell = false
history.persistence = "none"

[shell_environment_policy]
ignore_default_excludes = false

[shell_environment_policy.filters]
"*PROXY*" = "exclude"
"SCICONTEXT_PROMPT_FILE" = "exclude"

[features]
apps = false
plugins = false
remote_plugin = false
memories = false
multi_agent = false
hooks = false
browser_use = false
computer_use = false
shell_snapshot = false

[permissions.extract.filesystem]
":root" = "read"
{q(root)} = "read"
{q(root + '/outputs')} = "write"
{q(scratch)} = "write"
{q(control)} = "deny"
"/logs" = "deny"
"/proc" = "deny"

[permissions.extract.network]
enabled = false

[permissions.repair.filesystem]
":root" = "read"
{q(root)} = "write"
{q(scratch)} = "write"
{q(control)} = "deny"
"/logs" = "deny"
"/proc" = "deny"

[permissions.repair.network]
enabled = false
'''
