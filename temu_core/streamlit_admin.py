from __future__ import annotations

from datetime import datetime
import io
import json

import streamlit as st

from .auth import (
    backup_and_delete_local_user,
    ensure_local_user,
    is_registration_open,
    list_registered_users,
    list_user_backups,
    reset_local_user_password,
    set_local_user_role,
    set_local_user_status,
    set_registration_open,
)
from .billing import (
    create_admin_adjustment,
    create_redeem_batch,
    get_wallet_dashboard,
    list_pricing_rules,
    update_pricing_rule,
)
from .db import get_database_status, session_scope
from .models import EXPECTED_TABLES
from .settings import get_platform_settings
from .team import create_workspace_project, get_workspace_overview
from .usage import list_recent_usage_events


def render_platform_status_banner():
    settings = get_platform_settings()
    status = get_database_status(EXPECTED_TABLES)
    if not status["configured"]:
        st.info(
            "Team billing foundation is disabled. Set `DATABASE_URL` and `REDIS_URL` in Zeabur before enabling shared billing."
        )
        return status
    if not status["reachable"]:
        st.error(f"Team database is configured but unreachable: {status['error']}")
        return status
    if status["missing_tables"]:
        st.warning(
            "Team database is connected but the billing schema is missing. "
            "Run `alembic upgrade head` or set `PLATFORM_AUTO_MIGRATE=true` on Zeabur."
        )
        st.caption(f"Missing tables: {', '.join(status['missing_tables'])}")
        return status
    auto_migrate_label = "on" if settings.platform_auto_migrate else "off"
    st.success(
        f"Team database ready: {status['dialect']} · {status['table_count']} tables · auto-migrate {auto_migrate_label}"
    )
    return status


def _downloadable_code_buffer(batch_name: str, codes: list[str]) -> bytes:
    buf = io.StringIO()
    buf.write("batch_name,redeem_code\n")
    for code in codes:
        buf.write(f'"{batch_name}","{code}"\n')
    return buf.getvalue().encode("utf-8")


def render_billing_admin_tab():
    status = render_platform_status_banner()
    if not status["configured"] or not status["reachable"] or status["missing_tables"]:
        return

    with session_scope() as session:
        dashboard = get_wallet_dashboard(session)
        usage_events = list_recent_usage_events(session, limit=12)

    organization = dashboard["organization"]
    wallet = dashboard["wallet"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Workspace", organization.name)
    c2.metric("Wallet balance", f"{int(wallet.cached_balance):,} credits")
    c3.metric("Admin adjustments", f"{int(dashboard['total_topups']):,}")
    c4.metric("Usage debits", f"{int(dashboard['total_usage_debits']):,}")

    st.markdown("### Wallet adjustments")
    with st.form("wallet_adjustment_form", clear_on_submit=True):
        a1, a2 = st.columns(2)
        adjustment_type = a1.selectbox(
            "Adjustment type",
            ["admin_topup", "manual_adjustment", "manual_deduction"],
            format_func=lambda value: {
                "admin_topup": "Admin top-up",
                "manual_adjustment": "Manual credit",
                "manual_deduction": "Manual deduction",
            }[value],
        )
        amount = a2.number_input(
            "Credits", min_value=1, max_value=1_000_000, value=100, step=10
        )
        reason = st.text_area(
            "Reason", height=80, placeholder="Why is this balance being changed?"
        )
        submitted = st.form_submit_button(
            "Apply adjustment", type="primary", use_container_width=True
        )
        if submitted:
            signed_amount = int(amount)
            if adjustment_type == "manual_deduction":
                signed_amount = -signed_amount
            with session_scope() as session:
                result = create_admin_adjustment(
                    session,
                    amount=signed_amount,
                    operator_label="streamlit-admin",
                    reason=reason or adjustment_type,
                    adjustment_type=adjustment_type,
                )
            st.success(
                f"Wallet updated. New balance: {int(result['wallet_balance']):,} credits"
            )
            st.rerun()

    st.markdown("### Recent wallet ledger")
    ledger_rows = [
        {
            "time": entry.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "type": entry.entry_type,
            "delta": entry.amount_delta,
            "balance_after": entry.balance_after,
            "actor": entry.actor_label,
            "note": entry.note,
        }
        for entry in dashboard["recent_entries"]
    ]
    if ledger_rows:
        st.dataframe(ledger_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No wallet activity yet.")

    st.markdown("### Recent usage events")
    usage_rows = [
        {
            "time": event.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "feature": event.feature,
            "provider": event.provider,
            "model": event.model,
            "charge_source": event.charge_source,
            "requests": event.request_count,
            "images": event.output_images,
            "tokens": event.tokens_used,
        }
        for event in usage_events
    ]
    if usage_rows:
        st.dataframe(usage_rows, use_container_width=True, hide_index=True)
    else:
        st.caption(
            "Usage events will appear here after generation flows are wired into the new billing foundation."
        )


def render_redeem_code_admin_tab():
    status = render_platform_status_banner()
    if not status["configured"] or not status["reachable"] or status["missing_tables"]:
        return

    st.markdown("### Create redeem code batch")
    with st.form("redeem_batch_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        batch_name = c1.text_input(
            "Batch name", value=f"Ops {datetime.utcnow().strftime('%Y-%m-%d')}"
        )
        credits = c2.number_input(
            "Credits per code", min_value=1, max_value=1_000_000, value=100, step=10
        )
        code_count = c3.number_input(
            "Code count", min_value=1, max_value=5_000, value=10, step=1
        )
        d1, d2, d3 = st.columns(3)
        prefix = d1.text_input("Code prefix", value="TEMU")
        valid_days = d2.number_input(
            "Valid days", min_value=0, max_value=3650, value=30, step=1
        )
        notes = d3.text_input("Notes", value="")
        submitted = st.form_submit_button(
            "Generate batch", type="primary", use_container_width=True
        )
        if submitted:
            with session_scope() as session:
                result = create_redeem_batch(
                    session,
                    name=batch_name,
                    credit_amount=int(credits),
                    code_count=int(code_count),
                    operator_label="streamlit-admin",
                    prefix=prefix,
                    valid_days=int(valid_days),
                    notes=notes,
                )
            st.session_state["latest_redeem_batch"] = {
                "name": result.name,
                "credits": result.credit_amount,
                "count": result.created_count,
                "codes": result.codes,
            }
            st.success(f"Generated {result.created_count} redeem codes")
            st.rerun()

    latest_batch = st.session_state.get("latest_redeem_batch")
    if latest_batch:
        st.markdown("### Latest generated batch")
        st.caption(
            "Plaintext codes are only shown once. Download them now and store them securely."
        )
        st.code("\n".join(latest_batch["codes"][:50]), language="text")
        st.download_button(
            "Download CSV",
            data=_downloadable_code_buffer(latest_batch["name"], latest_batch["codes"]),
            file_name=f"redeem-batch-{latest_batch['name'].replace(' ', '-').lower()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with session_scope() as session:
        dashboard = get_wallet_dashboard(session)

    st.markdown("### Recent redeem code batches")
    batch_rows = [
        {
            "created_at": batch.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "name": batch.name,
            "credits_per_code": batch.credit_amount,
            "count": batch.code_count,
            "prefix": batch.code_prefix,
            "expires_at": batch.expires_at.strftime("%Y-%m-%d")
            if batch.expires_at
            else "never",
            "status": batch.status,
        }
        for batch in dashboard["recent_batches"]
    ]
    if batch_rows:
        st.dataframe(batch_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No redeem code batches yet.")


def render_workspace_admin_tab():
    status = render_platform_status_banner()
    if not status["configured"] or not status["reachable"] or status["missing_tables"]:
        return

    with session_scope() as session:
        overview = get_workspace_overview(session)

    organization = overview["organization"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Workspace", organization.name)
    c2.metric("Projects", overview["project_count"])
    c3.metric("Members", overview["member_count"])
    st.caption(
        "Members are auto-provisioned the first time they log in, so this phase avoids auth conflicts with the legacy JSON flow."
    )

    st.markdown("### Create project")
    with st.form("workspace_project_form", clear_on_submit=True):
        project_name = st.text_input("Project name", placeholder="Spring Campaign")
        submitted = st.form_submit_button(
            "Create project", type="primary", use_container_width=True
        )
        if submitted:
            if not project_name.strip():
                st.error("Project name is required")
            else:
                with session_scope() as session:
                    create_workspace_project(
                        session,
                        organization=organization,
                        name=project_name,
                        actor_label="streamlit-admin",
                    )
                st.success(f"Project created: {project_name}")
                st.rerun()

    st.markdown("### Projects")
    project_rows = [
        {
            "created_at": project.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "name": project.name,
            "status": project.status,
            "project_id": project.id,
        }
        for project in overview["projects"]
    ]
    if project_rows:
        st.dataframe(project_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No projects yet.")

    st.markdown("### Members")
    member_rows = [
        {
            "joined_at": member["joined_at"].strftime("%Y-%m-%d %H:%M:%S"),
            "username": member["username"],
            "display_name": member["display_name"],
            "role": member["role"],
            "status": member["status"],
        }
        for member in overview["members"]
    ]
    if member_rows:
        st.dataframe(member_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Members will appear after the first team login.")


def render_user_admin_tab():
    status = render_platform_status_banner()
    if not status["configured"] or not status["reachable"] or status["missing_tables"]:
        return

    with session_scope() as session:
        registration_open = is_registration_open(session)
        users = list_registered_users(session)
        backups = list_user_backups(session)

    c1, c2, c3 = st.columns(3)
    c1.metric("注册用户", len(users))
    c2.metric("注册状态", "开放" if registration_open else "已关闭")
    c3.metric("删除备份", len(backups))

    toggle_label = "一键停止注册" if registration_open else "一键开启注册"
    if st.button(toggle_label, use_container_width=True):
        with session_scope() as session:
            updated = set_registration_open(
                session,
                enabled=not registration_open,
                actor_label="streamlit-admin",
            )
        st.success("注册已开启" if updated else "注册已关闭")
        st.rerun()

    st.markdown("### 手动创建用户")
    with st.form("manual_create_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        username = c1.text_input("用户名")
        display_name = c2.text_input("显示名称")
        c3, c4, c5 = st.columns(3)
        email = c3.text_input("邮箱")
        role = c4.selectbox("角色", ["member", "admin"])
        password = c5.text_input("初始密码", type="password")
        submitted = st.form_submit_button(
            "创建用户", type="primary", use_container_width=True
        )
        if submitted:
            try:
                with session_scope() as session:
                    ensure_local_user(
                        session,
                        username=username,
                        password=password,
                        display_name=display_name,
                        email=email,
                        role=role,
                        actor_label="streamlit-admin",
                        allow_closed_registration=True,
                    )
                st.success(f"已创建用户 {username}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    st.markdown("### 注册用户管理")
    if not users:
        st.caption("暂无注册用户。")
    for user in users:
        title = f"{user['username']} · {user['role']} · {user['status']}"
        with st.expander(title):
            c1, c2, c3 = st.columns(3)
            c1.text_input(
                "显示名称",
                value=user["display_name"],
                disabled=True,
                key=f"user_name_{user['user_id']}",
            )
            c2.text_input(
                "邮箱",
                value=user["email"],
                disabled=True,
                key=f"user_email_{user['user_id']}",
            )
            c3.text_input(
                "最后登录",
                value=user["last_login_at"].strftime("%Y-%m-%d %H:%M:%S")
                if user["last_login_at"]
                else "从未登录",
                disabled=True,
                key=f"user_last_login_{user['user_id']}",
            )
            role_choice = st.selectbox(
                "角色",
                ["member", "admin"],
                index=0 if user["role"] == "member" else 1,
                key=f"role_choice_{user['user_id']}",
            )
            if st.button(
                "保存角色",
                key=f"save_role_{user['user_id']}",
                use_container_width=True,
            ):
                with session_scope() as session:
                    set_local_user_role(
                        session,
                        user_id=user["user_id"],
                        role=role_choice,
                        actor_label="streamlit-admin",
                        reason="admin_update_role",
                    )
                st.success("角色已更新")
                st.rerun()
            d1, d2, d3 = st.columns(3)
            if user["status"] == "active":
                if d1.button(
                    "停用用户",
                    key=f"disable_user_{user['user_id']}",
                    use_container_width=True,
                ):
                    with session_scope() as session:
                        set_local_user_status(
                            session,
                            user_id=user["user_id"],
                            status="disabled",
                            actor_label="streamlit-admin",
                            reason="admin_disable",
                        )
                    st.success("用户已停用")
                    st.rerun()
            else:
                if d1.button(
                    "恢复用户",
                    key=f"restore_user_{user['user_id']}",
                    use_container_width=True,
                ):
                    with session_scope() as session:
                        set_local_user_status(
                            session,
                            user_id=user["user_id"],
                            status="active",
                            actor_label="streamlit-admin",
                            reason="admin_restore",
                        )
                    st.success("用户已恢复")
                    st.rerun()

            new_password = d2.text_input(
                "重置密码",
                type="password",
                key=f"reset_password_input_{user['user_id']}",
            )
            if d2.button(
                "保存新密码",
                key=f"reset_password_btn_{user['user_id']}",
                use_container_width=True,
            ):
                try:
                    with session_scope() as session:
                        reset_local_user_password(
                            session,
                            user_id=user["user_id"],
                            new_password=new_password,
                            actor_label="streamlit-admin",
                        )
                    st.success("密码已重置")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

            delete_reason = d3.text_input(
                "删除原因",
                value="管理员删除",
                key=f"delete_reason_{user['user_id']}",
            )
            if d3.button(
                "备份并删除",
                key=f"delete_user_{user['user_id']}",
                use_container_width=True,
            ):
                try:
                    with session_scope() as session:
                        backup_and_delete_local_user(
                            session,
                            user_id=user["user_id"],
                            actor_label="streamlit-admin",
                            reason=delete_reason,
                        )
                    st.success("用户已备份并删除")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    st.markdown("### 删除备份")
    if not backups:
        st.caption("暂无用户备份。")
    for backup in backups[:20]:
        data = json.dumps(backup.snapshot_json or {}, ensure_ascii=False, indent=2)
        c1, c2 = st.columns([3, 1])
        c1.caption(
            f"{backup.username} · {backup.created_at.strftime('%Y-%m-%d %H:%M:%S')} · {backup.reason or '无原因'}"
        )
        c2.download_button(
            "下载备份",
            data=data.encode("utf-8"),
            file_name=f"user-backup-{backup.username}-{backup.created_at.strftime('%Y%m%d-%H%M%S')}.json",
            mime="application/json",
            key=f"download_backup_{backup.id}",
            use_container_width=True,
        )


def render_pricing_admin_tab():
    status = render_platform_status_banner()
    if not status["configured"] or not status["reachable"] or status["missing_tables"]:
        return

    with session_scope() as session:
        rules = list_pricing_rules(session)

    st.caption(
        "Pricing rules drive wallet debits for system-pool requests. BYOK requests keep stats but do not debit the shared wallet."
    )
    unit_options = ["per_output_image", "per_request", "per_1k_tokens", "flat"]
    status_options = ["active", "draft", "disabled"]
    for rule in rules:
        with st.expander(f"{rule.feature} · {rule.provider} · {rule.model}"):
            c1, c2, c3 = st.columns(3)
            price_amount = c1.number_input(
                "Price",
                min_value=0,
                max_value=1_000_000,
                value=int(rule.price_amount),
                step=1,
                key=f"pricing_amount_{rule.id}",
            )
            unit_type = c2.selectbox(
                "Unit type",
                unit_options,
                index=unit_options.index(rule.unit_type)
                if rule.unit_type in unit_options
                else 0,
                key=f"pricing_unit_{rule.id}",
            )
            status_value = c3.selectbox(
                "Status",
                status_options,
                index=status_options.index(rule.status)
                if rule.status in status_options
                else 0,
                key=f"pricing_status_{rule.id}",
            )
            notes = st.text_input(
                "Notes", value=rule.notes or "", key=f"pricing_notes_{rule.id}"
            )
            if st.button(
                "Save pricing rule",
                key=f"pricing_save_{rule.id}",
                use_container_width=True,
            ):
                with session_scope() as session:
                    update_pricing_rule(
                        session,
                        rule_id=rule.id,
                        price_amount=int(price_amount),
                        unit_type=unit_type,
                        status=status_value,
                        notes=notes,
                    )
                st.success("Pricing rule updated")
                st.rerun()
