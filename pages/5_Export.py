"""State App — export this state's data as CSV."""
import streamlit as st
import pandas as pd
from common import require_login, get_client, state_code

require_login()
sb = get_client()
st.title("Export — This State's Data")

staff = sb.table("staff").select("*").eq("state_code", state_code()).execute()
instances = (
    sb.table("test_instances")
    .select("*, staff!inner(state_code, level, designation, tu_name)")
    .eq("staff.state_code", state_code())
    .execute()
)

st.subheader("Staff records")
staff_df = pd.DataFrame(staff.data) if staff.data else pd.DataFrame()
st.dataframe(staff_df, use_container_width=True)
if not staff_df.empty:
    st.download_button(
        "Download staff.csv",
        staff_df.to_csv(index=False),
        file_name=f"staff_{state_code()}.csv",
        mime="text/csv",
    )

st.subheader("Test instances (pre/post, scores)")
inst_df = pd.json_normalize(instances.data) if instances.data else pd.DataFrame()
st.dataframe(inst_df, use_container_width=True)
if not inst_df.empty:
    st.download_button(
        "Download test_instances.csv",
        inst_df.to_csv(index=False),
        file_name=f"test_instances_{state_code()}.csv",
        mime="text/csv",
    )
