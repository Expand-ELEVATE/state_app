"""State App — generate pre/post test instances for staff IDs.

Single mode: one ID, choose pre/post/both.
Bulk mode: CSV of staff_id + stage (pre/post/both), one row per ID.
"""
import streamlit as st
import pandas as pd
from common import require_login, get_client, state_code

require_login()
sb = get_client()
st.title("Generate Tests")

staff_rows = sb.table("staff").select("id, level, designation").eq("state_code", state_code()).execute()
staff_options = [r["id"] for r in staff_rows.data] if staff_rows.data else []
valid_staff_ids = set(staff_options)

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


def create_instance(staff_id: str, stage: str) -> tuple[bool, str]:
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
        return True, ""
    except Exception as e:
        # Most likely: unique(staff_id, questionnaire_id, stage) already exists.
        return False, str(e)


tab_single, tab_bulk = st.tabs(["Single staff ID", "Bulk upload (CSV)"])

with tab_single:
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
                ok, err = create_instance(staff_id, stage)
                if ok:
                    created.append(stage)
                else:
                    st.warning(f"Could not create '{stage}' instance (maybe already exists): {err}")
            if created:
                st.success(f"Created instance(s): {', '.join(created)} for staff ID {staff_id}")

with tab_bulk:
    st.subheader("Bulk-generate tests from CSV")
    st.markdown(
        """
        Upload a CSV with exactly these columns (one row per staff ID):

        `staff_id, stage`

        - `staff_id` must be an existing ID already created on the
          'Manage Staff IDs' page.
        - `stage` must be `pre`, `post`, or `both` (both creates one pre
          AND one post instance for that row).
        """
    )
    uploaded = st.file_uploader("Upload test-generation CSV", type="csv", key="bulk_test_csv")

    if uploaded:
        df = pd.read_csv(uploaded)
        required_cols = {"staff_id", "stage"}
        if not required_cols.issubset(df.columns):
            st.error(f"Missing required columns: {required_cols - set(df.columns)}")
        else:
            df["staff_id"] = df["staff_id"].astype(str).str.strip()
            df["stage"] = df["stage"].astype(str).str.strip().str.lower()

            unknown_ids = sorted(set(df["staff_id"]) - valid_staff_ids)
            bad_stage = sorted(set(df["stage"]) - {"pre", "post", "both"})

            if unknown_ids:
                st.error(f"Unknown staff ID(s) (not found for this state): {unknown_ids}")
            elif bad_stage:
                st.error(f"Invalid stage value(s): {bad_stage}. Must be 'pre', 'post', or 'both'.")
            else:
                st.dataframe(df, use_container_width=True)
                if st.button(f"Generate tests for {len(df)} row(s)"):
                    results = []
                    for _, row in df.iterrows():
                        sid = row["staff_id"]
                        stages_to_make = ["pre", "post"] if row["stage"] == "both" else [row["stage"]]
                        for stage in stages_to_make:
                            ok, err = create_instance(sid, stage)
                            results.append(
                                {"staff_id": sid, "stage": stage, "status": "created" if ok else "skipped/error"}
                            )
                    result_df = pd.DataFrame(results)
                    st.success(f"Processed {len(df)} row(s), {len(result_df)} instance(s) attempted.")
                    st.dataframe(result_df, use_container_width=True)
                    st.download_button(
                        "Download result log as CSV",
                        result_df.to_csv(index=False),
                        file_name=f"bulk_test_generation_log_{state_code()}.csv",
                        mime="text/csv",
                    )

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
