"""State App — staff test-taking screen. NO login, ID only.

This page must NOT call require_login() — staff never authenticate.
All access goes through the SECURITY DEFINER RPCs defined in schema.sql,
which do their own authorization check against the supplied staff ID.
"""
import streamlit as st
from common import get_client, render_question_markdown, escape_markdown

st.set_page_config(page_title="Take Test")
sb = get_client()

st.title("Expand ELEVATE — Take Your Test")
st.caption("Enter the ID given to you by your state data analyst. No name or login needed.")

if "test_instance_id" not in st.session_state:
    staff_id = st.text_input("Your ID")
    if st.button("Start"):
        res = sb.rpc("staff_get_pending_test", {"p_staff_id": staff_id.strip()}).execute()
        if not res.data:
            st.error("No pending test found for this ID. Check the ID and try again, or contact your state analyst.")
        else:
            row = res.data[0]
            st.session_state["test_instance_id"] = row["test_instance_id"]
            st.session_state["stage"] = row["stage"]
            st.rerun()
    st.stop()

test_instance_id = st.session_state["test_instance_id"]
st.info(f"Stage: **{st.session_state['stage'].upper()}-TEST**")

q_res = sb.rpc("staff_get_questions", {"p_test_instance_id": test_instance_id}).execute()
questions = q_res.data or []

if not questions:
    st.error("No questions found for this test. Contact your state analyst.")
    st.stop()

answers = {}
with st.form("test_form"):
    for q in questions:
        st.markdown(f"Q{q['question_no']}. {render_question_markdown(q['question_text'])}")
        choice = st.radio(
            f"q_{q['question_no']}",
            options=["A", "B", "C", "D"],
            index=None,  # no option pre-selected — staff must actively choose
            format_func=lambda opt, q=q: f"{opt}. {escape_markdown(q[f'option_{opt.lower()}'])}",
            key=f"q_{q['question_no']}",
            label_visibility="collapsed",
        )
        answers[q["question_no"]] = choice
        st.divider()
    submit = st.form_submit_button("Submit Test")

if submit:
    unanswered = [qn for qn, opt in answers.items() if opt is None]
    if unanswered:
        st.error(
            f"Please answer all questions before submitting. "
            f"Missing: Q{', Q'.join(str(q) for q in sorted(unanswered))}"
        )
        st.stop()
    payload = [{"question_no": qn, "selected_option": opt} for qn, opt in answers.items()]
    result = sb.rpc("staff_submit_test", {"p_test_instance_id": test_instance_id, "p_answers": payload}).execute()
    if result.data:
        st.success("Test submitted. Thank you!")
        st.balloons()
        del st.session_state["test_instance_id"]
        del st.session_state["stage"]
    else:
        st.error("Submission failed — please contact your state analyst.")
