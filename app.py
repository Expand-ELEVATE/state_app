"""Expand ELEVATE — State App entry point."""
import streamlit as st
from common import require_login, state_code

st.set_page_config(page_title="Expand ELEVATE — State App", layout="wide")

require_login()

st.title("Expand ELEVATE — State App")
st.caption(f"State: {state_code()}")

st.markdown(
    """
    Use the sidebar pages to:
    - **Manage Staff IDs** — create anonymous staff records and generate login IDs
    - **Generate Tests** — assign pre-test / post-test instances to new or existing staff IDs
    - **Take Test** — the screen a staff member uses with just their ID (no login)
    - **Questionnaire** — choose default or upload a translated CSV version
    - **Export** — download this state's data as CSV
    """
)

if st.button("Log out"):
    from common import get_client
    get_client().auth.sign_out()
    st.session_state.clear()
    st.rerun()
