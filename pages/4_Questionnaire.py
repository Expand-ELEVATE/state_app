"""State App — choose default questionnaire or upload a translated CSV."""
import streamlit as st
import pandas as pd
from common import require_login, get_client, state_code

require_login()
sb = get_client()
st.title("Questionnaire")

qmeta = sb.table("questionnaire_meta").select("*").eq("is_active", True).limit(1).execute()
if not qmeta.data:
    st.error("No active questionnaire exists. Ask the national admin to create one first.")
    st.stop()
questionnaire_id = qmeta.data[0]["id"]
st.caption(f"Active questionnaire: **{qmeta.data[0]['title']}**")

default_qs = (
    sb.table("questions")
    .select("question_no, question_text, option_a, option_b, option_c, option_d")
    .eq("questionnaire_id", questionnaire_id)
    .order("question_no")
    .execute()
)
st.subheader("Default (national) questionnaire")
st.dataframe(pd.DataFrame(default_qs.data), use_container_width=True)

st.divider()
st.subheader("Upload a translated version (optional)")
st.markdown(
    """
    The CSV **must** have exactly these columns, one row per question, and
    must map 1:1 to the default questionnaire above by `question_no`:

    `question_no, question_text, option_a, option_b, option_c, option_d, language_name`

    - Question wording and option wording may be translated freely.
    - Do **not** change the number of questions or their `question_no` values.
    - The correct answer is always inherited from the national default —
      you cannot change which option is correct via translation.
    """
)

uploaded = st.file_uploader("Upload translated questionnaire CSV", type="csv")
if uploaded:
    df = pd.read_csv(uploaded)
    required_cols = {"question_no", "question_text", "option_a", "option_b", "option_c", "option_d", "language_name"}
    if not required_cols.issubset(df.columns):
        st.error(f"CSV is missing required columns: {required_cols - set(df.columns)}")
    else:
        default_nos = {r["question_no"] for r in default_qs.data}
        upload_nos = set(df["question_no"])
        if upload_nos != default_nos:
            st.error(
                f"question_no values must exactly match the default questionnaire. "
                f"Missing: {default_nos - upload_nos}, Extra: {upload_nos - default_nos}"
            )
        else:
            st.dataframe(df, use_container_width=True)
            if st.button("Confirm and save translated questionnaire"):
                records = [
                    {
                        "questionnaire_id": questionnaire_id,
                        "state_code": state_code(),
                        "question_no": int(row["question_no"]),
                        "question_text": row["question_text"],
                        "option_a": row["option_a"],
                        "option_b": row["option_b"],
                        "option_c": row["option_c"],
                        "option_d": row["option_d"],
                        "language_name": row["language_name"],
                    }
                    for _, row in df.iterrows()
                ]
                sb.table("state_questionnaire_translations").upsert(
                    records, on_conflict="questionnaire_id,state_code,question_no"
                ).execute()
                st.success("Translated questionnaire saved. Select 'translated' when generating tests.")
