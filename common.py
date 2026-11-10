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
            .maybe_single()
            .execute()
        )
        prof = profile.data if profile else None
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


def generate_staff_id(length: int = 6) -> str:
    """Short random alphanumeric ID — unguessable, no link to any identity.
    6 chars of A-Z0-9 (36^6 ≈ 2.18 billion combinations) is comfortably
    collision-safe at the scale of thousands of staff per state; callers
    still retry on collision as a safety net."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def fetch_all(build_query, page_size: int = 1000) -> list[dict]:
    """Page through a Supabase/PostgREST query until all rows are fetched.

    PostgREST (and therefore supabase-py) silently caps any query at 1000
    rows by default — a plain .select("*").execute() on a large table
    returns only the first 1000 with NO error, which looks like "working
    fine" right up until a state crosses that row count. This loops with
    .range() until a short page signals the end.

    `build_query` must be a zero-arg callable that returns a FRESH query
    builder each call (e.g. `lambda: sb.table("staff").select("*")`),
    because supabase-py query objects are consumed once .execute()'d.
    """
    rows: list[dict] = []
    offset = 0
    while True:
        res = build_query().range(offset, offset + page_size - 1).execute()
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def escape_markdown(text) -> str:
    """Escape markdown/LaTeX-special characters so plain data renders as
    literal text in st.markdown / widget labels, instead of being
    misinterpreted as formatting.

    This matters because question/option text can contain Excel-formula
    style content like "$A$2" or "=A2*B2" — Streamlit's markdown renderer
    treats a PAIR of $ as a LaTeX math span (so "$A$2" renders "A" in
    italic math mode, not as the literal cell reference), and a bare *
    can trigger italics/bold. Escaping with a backslash makes these render
    as plain, literal text.
    """
    if text is None:
        return ""
    s = str(text)
    # Backslash must be escaped FIRST, or the escapes added below for the
    # other characters would themselves get double-escaped.
    for ch in ["\\", "$", "_", "`", "#", "~"]:
        s = s.replace(ch, "\\" + ch)
    return s


def render_question_markdown(text) -> str:
    """Render question text for display, allowing question authors to bold
    specific IMPORTANT WORDS by wrapping them in **double asterisks** in
    the source CSV — everything else (including $ _ ` # ~ characters that
    may appear in Excel-formula-style text) is escaped so it renders as
    literal plain text rather than unintended markdown/LaTeX formatting.

    Only use this for question_text, which is meant to support authored
    bolding. Use escape_markdown() alone for option text, which should
    never be bolded/formatted.
    """
    if text is None:
        return ""
    import re

    parts = re.split(r"(\*\*.+?\*\*)", str(text))
    rendered = []
    for part in parts:
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            rendered.append(f"**{escape_markdown(part[2:-2])}**")
        else:
            rendered.append(escape_markdown(part))
    return "".join(rendered)
