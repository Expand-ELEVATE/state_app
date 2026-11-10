"""State App — create anonymous staff records and generate their login ID."""
import streamlit as st
import pandas as pd
from common import require_login, get_client, state_code, generate_staff_id

require_login()
sb = get_client()
st.title("Manage Staff IDs")

LEVELS = ["State", "District", "IRL Lab", "NRL Lab", "STDC", "TB Unit"]

with st.form("new_staff"):
    st.subheader("Create a new staff ID")
    level = st.selectbox("Level", LEVELS)
    designation = st.text_input("Designation")
    tu_name = st.text_input("TU name (only if applicable)", value="")
    submitted = st.form_submit_button("Generate ID")

if submitted:
    if not designation.strip():
        st.error("Designation is required.")
    else:
        new_id = generate_staff_id()
        # Retry on the rare collision with existing ID.
        for _ in range(5):
            exists = sb.table("staff").select("id").eq("id", new_id).execute()
            if not exists.data:
                break
            new_id = generate_staff_id()

        sb.table("staff").insert(
            {
                "id": new_id,
                "state_code": state_code(),
                "level": level,
                "designation": designation.strip(),
                "tu_name": tu_name.strip() or None,
                "created_by": st.session_state["sb_user_id"],
            }
        ).execute()
        st.success(f"Staff ID created: **{new_id}**  — share this with the staff member out-of-band.")

st.divider()
st.subheader(f"Existing staff IDs — {state_code()}")

rows = sb.table("staff").select("*").eq("state_code", state_code()).order("created_at", desc=True).execute()
if rows.data:
    st.dataframe(pd.DataFrame(rows.data), use_container_width=True)
else:
    st.info("No staff IDs created yet.")
