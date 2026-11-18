import streamlit as st
from pages.helper import db_queries

st.set_page_config(page_title="Track Report", page_icon="🔎")

# Ensure DB schema is initialized/migrated even if opened directly
db_queries.create_db()

STAGES = [
    "Case Registered",
    "Under Verification",
    "Investigation in Progress",
    "Search in Progress",
    "Person Found",
    "Case Closed",
]

st.title("🔎 Track Report")
st.write(
    "Enter the **Docket Number** provided at the time of case registration to track live case progress."
)

default_docket = st.session_state.get("tracked_docket_input", "")

with st.form("track_report_form"):
    docket_no = st.text_input(
        "Docket Number *",
        value=default_docket,
        placeholder="e.g. MP-20261118-ABC123",
    )
    submitted = st.form_submit_button("Track Progress", type="primary")

if submitted:
    if not docket_no.strip():
        st.warning("Please enter your Docket Number.")
    else:
        st.session_state["tracked_docket_input"] = docket_no.strip().upper()

active_docket = st.session_state.get("tracked_docket_input", "")

if active_docket:
    case = db_queries.get_case_by_docket(active_docket)
    if not case:
        st.error(
            f"No report found for Docket Number **{active_docket}**. Please verify the number and try again."
        )
    else:
        st.success(f"Report found for Docket Number: **{case.docket_no}**")

        current_stage = case.progress_stage or "Case Registered"
        stage_idx = STAGES.index(current_stage) if current_stage in STAGES else 0
        progress_pct = int(((stage_idx + 1) / len(STAGES)) * 100)

        c1, c2, c3 = st.columns(3)
        c1.metric("Docket Number", case.docket_no)
        c2.metric("Case Status", "Person Found" if case.status == "F" else "Search Ongoing")
        c3.metric("Current Stage", current_stage)

        st.progress(progress_pct / 100, text=f"Overall Progress: {progress_pct}%")

        info_col, img_col = st.columns([3, 1])
        with info_col:
            st.write(f"**Missing Person Name:** {case.name}")
            st.write(f"**Age:** {case.age or 'N/A'}")
            st.write(f"**City:** {case.city or 'Not specified'}")
            st.write(f"**Last Seen:** {case.last_seen}")
            st.write(
                f"**Registered On:** "
                f"{case.submitted_on.strftime('%d %b %Y, %I:%M %p') if case.submitted_on else 'N/A'}"
            )
            if case.progress_note:
                st.info(f"**Latest Officer Update:** {case.progress_note}")

        with img_col:
            try:
                st.image(f"./resources/{case.id}.jpg", width=130, use_container_width=False)
            except Exception:
                st.caption("No photo available")

        st.markdown("### Progress Timeline")
        for i, stage in enumerate(STAGES):
            if stage == current_stage:
                st.markdown(f"🟢 **{stage}** — *(Current Stage)*")
            elif i < stage_idx:
                st.markdown(f"✅ {stage}")
            else:
                st.markdown(f"⚪ {stage}")

# ── Officer / Admin Progress Update Panel ─────────────────────────────────────
if st.session_state.get("login_status") and st.session_state.get("authentication_status"):
    st.divider()
    st.subheader("Officer / Admin: Update Case Progress")
    with st.form("update_progress_form"):
        update_docket = st.text_input(
            "Docket Number to Update *",
            value=active_docket,
            placeholder="MP-20261118-ABC123",
            key="update_docket",
        )
        default_stage_idx = 0
        if active_docket:
            existing = db_queries.get_case_by_docket(active_docket)
            if existing and existing.progress_stage in STAGES:
                default_stage_idx = STAGES.index(existing.progress_stage)

        stage = st.selectbox("New Progress Stage", STAGES, index=default_stage_idx)
        note = st.text_area(
            "Progress Update / Remarks (optional)",
            max_chars=512,
            placeholder="Enter investigation notes or status remarks...",
        )
        update_btn = st.form_submit_button("💾 Save Progress Update", type="primary")

    if update_btn:
        if not update_docket.strip():
            st.warning("Please enter a Docket Number.")
        elif db_queries.update_case_progress(update_docket, stage, note.strip()):
            st.session_state["tracked_docket_input"] = update_docket.strip().upper()
            st.success(f"✅ Progress updated to **{stage}** for `{update_docket.strip().upper()}`.")
            st.rerun()
        else:
            st.error("Docket Number not found.")
