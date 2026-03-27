from __future__ import annotations


def get_runtime_mode(has_database_url: bool, team_ready: bool) -> str:
    if has_database_url and team_ready:
        return "team_mode"
    return "admin_tool_mode"


def should_show_team_features(runtime_mode: str) -> bool:
    return runtime_mode == "team_mode"


def should_force_registered_login(
    runtime_mode: str,
    is_admin: bool,
    use_own_key: bool,
    has_auth_user_id: bool,
) -> bool:
    return (
        runtime_mode == "team_mode"
        and not is_admin
        and not use_own_key
        and not has_auth_user_id
    )


def describe_session_mode(
    is_admin: bool, use_own_key: bool, has_auth_user_id: bool
) -> str:
    if is_admin:
        return "管理员模式"
    if use_own_key:
        return "个人模式"
    if has_auth_user_id:
        return "团队模式"
    return "未登录"
