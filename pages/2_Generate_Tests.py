"""State App — generate pre/post test instances for staff IDs.

Single mode: one ID, choose pre/post/both.
Bulk mode: CSV of staff_id + stage (pre/post/both), one row per ID.
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from common import require_login, get_client, state_code, fetch_all

require_login()
sb = get_client()
st.title("Generate Tests")

staff_rows = fetch_all(
    lambda: sb.table("staff").select("id, level, designation").eq("state_code", state_code())
)
staff_options = [r["id"] for r in staff_rows]
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
instances = fetch_all(
    lambda: sb.table("test_instances")
    .select("*, staff!inner(state_code)")
    .eq("staff.state_code", state_code())
    .order("assigned_at", desc=True)
)
if instances:
    df = pd.json_normalize(instances)
    st.dataframe(df, use_container_width=True)
else:
    st.info("No test instances yet.")

st.divider()
st.subheader("Revoke test instances")
st.markdown(
    """
    Revoking marks an instance as `revoked` rather than deleting it — the
    historical record stays visible, and a fresh instance can be generated
    afterward for the same staff ID + stage if needed. Only `assigned`
    (not yet completed) instances can usefully be revoked; completed ones
    are revoked the same way but their score stays in the record for audit.
    """
)

revocable = [i for i in instances if i.get("status") != "revoked"]

tab_revoke_single, tab_revoke_bulk = st.tabs(["Revoke single instance(s)", "Bulk revoke (CSV)"])

with tab_revoke_single:
    if not revocable:
        st.info("No active instances to revoke.")
    else:
        labels = {
            f"{i['staff_id']} — {i['stage']} — {i['status']} (assigned {i['assigned_at'][:10]})": i["id"]
            for i in revocable
        }
        picked = st.multiselect("Select instance(s) to revoke", list(labels.keys()))
        if picked and st.button("Revoke selected", type="primary"):
            now_iso = datetime.now(timezone.utc).isoformat()
            for label in picked:
                sb.table("test_instances").update(
                    {"status": "revoked", "revoked_at": now_iso}
                ).eq("id", labels[label]).execute()
            st.success(f"Revoked {len(picked)} instance(s).")
            st.rerun()

with tab_revoke_bulk:
    st.markdown(
        """
        Upload a CSV with exactly these columns (one row per instance to revoke):

        `staff_id, stage`

        Only the currently ACTIVE (non-revoked) instance for that
        staff_id + stage is revoked.
        """
    )
    uploaded_revoke = st.file_uploader("Upload revoke CSV", type="csv", key="bulk_revoke_csv")

    if uploaded_revoke:
        rdf = pd.read_csv(uploaded_revoke)
        required_cols = {"staff_id", "stage"}
        if not required_cols.issubset(rdf.columns):
            st.error(f"Missing required columns: {required_cols - set(rdf.columns)}")
        else:
            rdf["staff_id"] = rdf["staff_id"].astype(str).str.strip()
            rdf["stage"] = rdf["stage"].astype(str).str.strip().str.lower()
            bad_stage = sorted(set(rdf["stage"]) - {"pre", "post"})
            if bad_stage:
                st.error(f"Invalid stage value(s): {bad_stage}. Must be 'pre' or 'post'.")
            else:
                st.dataframe(rdf, use_container_width=True)
                if st.button(f"Revoke {len(rdf)} instance(s)"):
                    by_key = {(i["staff_id"], i["stage"]): i["id"] for i in revocable}
                    now_iso = datetime.now(timezone.utc).isoformat()
                    results = []
                    for _, row in rdf.iterrows():
                        key = (row["staff_id"], row["stage"])
                        if key in by_key:
                            sb.table("test_instances").update(
                                {"status": "revoked", "revoked_at": now_iso}
                            ).eq("id", by_key[key]).execute()
                            results.append({**row.to_dict(), "status": "revoked"})
                        else:
                            results.append({**row.to_dict(), "status": "no active instance found"})
                    result_df = pd.DataFrame(results)
                    st.success(f"Processed {len(rdf)} row(s).")
                    st.dataframe(result_df, use_container_width=True)
                    st.download_button(
                        "Download revoke result log as CSV",
                        result_df.to_csv(index=False),
                        file_name=f"bulk_revoke_log_{state_code()}.csv",
                        mime="text/csv",
                    )
