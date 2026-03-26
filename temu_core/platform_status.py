from __future__ import annotations


def describe_platform_database_status(
    status: dict, auto_migrate: bool = False, has_service_access: bool = False
) -> dict:
    if not status.get("configured"):
        if has_service_access:
            return {
                "state": "optional_database_missing",
                "level": "info",
                "ready": False,
                "message": "团队数据库未启用，但管理员/系统服务仍可用。",
                "detail": "当前可以先用管理员登录和系统中转站；只有注册用户、钱包、团队项目等功能需要 DATABASE_URL。",
            }
        return {
            "state": "missing_database_url",
            "level": "warning",
            "ready": False,
            "message": "团队数据库未配置：请在 Zeabur 模板或服务变量中提供 `DATABASE_URL`。",
            "detail": "推荐使用 template-first 部署，自动注入 `POSTGRES_CONNECTION_STRING`。",
        }

    if not status.get("reachable"):
        error_text = str(status.get("error") or "").strip() or "数据库连接失败"
        return {
            "state": "database_unreachable",
            "level": "error",
            "ready": False,
            "message": "团队数据库已配置，但当前无法连接。",
            "detail": error_text,
        }

    missing_tables = list(status.get("missing_tables") or [])
    if missing_tables:
        suffix = (
            "当前已开启 `PLATFORM_AUTO_MIGRATE`，请检查迁移日志。"
            if auto_migrate
            else "请开启 `PLATFORM_AUTO_MIGRATE=true` 或手动执行 `alembic upgrade head`。"
        )
        return {
            "state": "missing_tables",
            "level": "warning",
            "ready": False,
            "message": "团队数据库可连接，但表结构未初始化完成。",
            "detail": f"缺少数据表: {', '.join(missing_tables)}。{suffix}",
        }

    dialect = str(status.get("dialect") or "database")
    table_count = int(status.get("table_count") or 0)
    return {
        "state": "ready",
        "level": "success",
        "ready": True,
        "message": f"团队数据库已就绪：{dialect} · {table_count} 张表。",
        "detail": "注册用户体系、钱包、项目和兑换码功能均可用。",
    }
