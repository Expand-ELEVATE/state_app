"""State App — generate pre/post test instances for a staff ID."""
import streamlit as st
import pandas as pd
from common import require_login, get_client, state_code

require_login()
sb = get_client()
st.title("Generate Tests")

staff_rows = sb.table("staff").select("id, level, designation").eq("state_code", state_code()).execute()
staff_options = [r["id"] for r in staff_rows.data] if staff_rows.data else []

qmeta = sb.table("questionnaire_meta").select("*").eq("is_active", True).limit(1).execute()
if not qmeta.data:
    st.error("No active questionnaire exists yet. Ask the national admin to create one.")
    st.stop()
questionnaire_id = qmeta.data[0]["id"]
st.caption(f"Active questionnaire: **{qmeta.data[0]['title']}**")

language = st.radio("Questionnaire language", ["default", "translated"], horizontal=True)
if language == "translated":
    trans = (
        sb.table("state_questionnaire_translations")
        .select("question_no")
        .eq("state_code", state_code())
        .eq("questionnaire_id", questionnaire_id)
        .execute()
    )
    if not trans.data:
        st.warning(
            "No translated questionnaire uploaded for your state yet. "
            "Go to the Questionnaire page to upload one, or use 'default'."
        )

with st.form("gen_test"):
    staff_id = st.selectbox("Staff ID", staff_options) if staff_options else st.text_input("Staff ID")
    stages = st.multiselect("Generate instance(s) for", ["pre", "post"], default=["pre"])
    submitted = st.form_submit_button("Generate")

if submitted:
    if not staff_id or not stages:
        st.error("Pick a staff ID and at least one stage.")
    else:
        created = []
        for stage in stages:
            try:
                sb.table("test_instances").insert(
                    {
                        "staff_id": staff_id,
                        "questionnaire_id": questionnaire_id,
                        "stage": stage,
                        "language_used": language,
                        "status": "assigned",
                    }
                ).execute()
                created.append(stage)
            except Exception as e:
                # Most likely: unique(staff_id, questionnaire_id, stage) already exists.
                st.warning(f"Could not create '{stage}' instance (maybe already exists): {e}")
        if created:
            st.success(f"Created instance(s): {', '.join(created)} for staff ID {staff_id}")

st.divider()
st.subheader("All test instances — this state")
instances = (
    sb.table("test_instances")
    .select("*, staff!inner(state_code)")
    .eq("staff.state_code", state_code())
    .order("assigned_at", desc=True)
    .execute()
)
if instances.data:
    df = pd.json_normalize(instances.data)
    st.dataframe(df, use_container_width=True)
else:
    st.info("No test instances yet.")
