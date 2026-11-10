"""State App — create anonymous staff records and generate their login ID.

Two modes: single staff creation, and bulk creation via CSV upload.
No identifying details are ever collected — only Level, Designation, and
whether the staff member is attached to a TU (Yes/No, no TU name).
"""
import streamlit as st
import pandas as pd
from common import require_login, get_client, state_code, generate_staff_id

require_login()
sb = get_client()
st.title("Manage Staff IDs")

LEVELS = ["State", "District", "IRL Lab", "NRL Lab", "STDC", "TB Unit"]


def unique_new_id(existing_ids: set) -> str:
    new_id = generate_staff_id()
    while new_id in existing_ids:
        new_id = generate_staff_id()
    existing_ids.add(new_id)
    return new_id


tab_single, tab_bulk = st.tabs(["Single staff ID", "Bulk upload (CSV)"])

with tab_single:
    with st.form("new_staff"):
        st.subheader("Create a new staff ID")
        level = st.selectbox("Level", LEVELS)
        designation = st.text_input("Designation")
        tu = st.radio("TU (Tuberculosis Unit)?", ["No", "Yes"], horizontal=True)
        submitted = st.form_submit_button("Generate ID")

    if submitted:
        if not designation.strip():
            st.error("Designation is required.")
        else:
            existing = sb.table("staff").select("id").execute()
            existing_ids = {r["id"] for r in (existing.data or [])}
            new_id = unique_new_id(existing_ids)

            sb.table("staff").insert(
                {
                    "id": new_id,
                    "state_code": state_code(),
                    "level": level,
                    "designation": designation.strip(),
                    "tu": tu == "Yes",
                    "created_by": st.session_state["sb_user_id"],
                }
            ).execute()
            st.success(f"Staff ID created: **{new_id}**  — share this with the staff member out-of-band.")

with tab_bulk:
    st.subheader("Bulk-create staff IDs from CSV")
    st.markdown(
        f"""
        Upload a CSV with exactly these columns (one row per staff member):

        `Level, Designation, TU`

        - `Level` must be one of: {', '.join(LEVELS)}
        - `TU` must be `Yes` or `No`
        - Do **not** include any name, phone number, or other identifying
          detail — this app only ever tracks Level, Designation, and TU
          status. The state DA's own records (kept outside this app) are
          what links a login ID back to a real person, if ever needed.

        A random 6-character login ID is generated for every row. Download
        the result immediately after upload — it is not shown again later
        on this page (though it always remains visible in the table below).
        """
    )
    uploaded = st.file_uploader("Upload staff CSV", type="csv", key="bulk_staff_csv")

    if uploaded:
        df = pd.read_csv(uploaded)
        required_cols = {"Level", "Designation", "TU"}
        if not required_cols.issubset(df.columns):
            st.error(f"Missing required columns: {required_cols - set(df.columns)}")
        else:
            bad_levels = sorted(set(df["Level"]) - set(LEVELS))
            bad_tu = sorted(set(df["TU"].astype(str).str.strip().str.capitalize()) - {"Yes", "No"})
            if bad_levels:
                st.error(f"Invalid Level value(s): {bad_levels}. Must be one of {LEVELS}.")
            elif bad_tu:
                st.error(f"Invalid TU value(s): {bad_tu}. Must be 'Yes' or 'No'.")
            else:
                st.dataframe(df, use_container_width=True)
                if st.button(f"Create {len(df)} staff ID(s)"):
                    existing = sb.table("staff").select("id").execute()
                    existing_ids = {r["id"] for r in (existing.data or [])}

                    records = []
                    for _, row in df.iterrows():
                        new_id = unique_new_id(existing_ids)
                        records.append(
                            {
                                "id": new_id,
                                "state_code": state_code(),
                                "level": row["Level"],
                                "designation": str(row["Designation"]).strip(),
                                "tu": str(row["TU"]).strip().capitalize() == "Yes",
                                "created_by": st.session_state["sb_user_id"],
                            }
                        )

                    sb.table("staff").insert(records).execute()
                    result_df = pd.DataFrame(records)[["id", "level", "designation", "tu"]]
                    st.success(f"Created {len(records)} staff IDs.")
                    st.dataframe(result_df, use_container_width=True)
                    st.download_button(
                        "Download generated IDs as CSV",
                        result_df.to_csv(index=False),
                        file_name=f"new_staff_ids_{state_code()}.csv",
                        mime="text/csv",
                    )

st.divider()
st.subheader(f"Existing staff IDs — {state_code()}")

rows = sb.table("staff").select("*").eq("state_code", state_code()).order("created_at", desc=True).execute()
if rows.data:
    st.dataframe(pd.DataFrame(rows.data), use_container_width=True)
else:
    st.info("No staff IDs created yet.")
