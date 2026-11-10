"""Supabase client + auth helpers shared by state_app pages."""
import secrets
import string
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)


def state_code() -> str:
    return st.secrets["STATE_CODE"]


def login_screen():
    """Supabase Auth email/password login, gated to this app's own state_code."""
    st.title("Expand ELEVATE — State Login")
    st.caption(f"Deployment fixed to state: **{state_code()}**")

    if "sb_session" in st.session_state:
        return True

    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        sb = get_client()
        try:
            res = sb.auth.sign_in_with_password({"email": email, "password": password})
        except Exception as e:
            st.error(f"Login failed: {e}")
            return False

        profile = (
            sb.table("admin_profiles")
            .select("role, state_code")
            .eq("user_id", res.user.id)
            .single()
            .execute()
        )
        prof = profile.data
        if not prof or prof["role"] != "state":
            st.error("This account is not a State admin account.")
            sb.auth.sign_out()
            return False
        if prof["state_code"] != state_code():
            st.error(
                f"This account belongs to state '{prof['state_code']}', "
                f"not this deployment's state '{state_code()}'."
            )
            sb.auth.sign_out()
            return False

        st.session_state["sb_session"] = res.session
        st.session_state["sb_user_id"] = res.user.id
        st.rerun()

    return False


def require_login():
    if not login_screen():
        st.stop()


def generate_staff_id(length: int = 10) -> str:
    """Long random alphanumeric ID — unguessable, no link to any identity."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
