from __future__ import annotations

from datetime import datetime
import io

import streamlit as st

from .billing import create_admin_adjustment, create_redeem_batch, get_wallet_dashboard
from .db import get_database_status, session_scope
from .models import EXPECTED_TABLES
from .settings import get_platform_settings
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
    c4.metric("Redeemed credits", f"{int(dashboard['total_redeemed']):,}")

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
