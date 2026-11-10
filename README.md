# Expand ELEVATE — State App

Streamlit app deployed **independently by each state's own data analyst**
on their own free Streamlit Community Cloud account. Code is public;
your state's credentials are never committed — they live only in
Streamlit Cloud's Secrets manager.

## Setup (per state)

1. Deploy this repo on [Streamlit Community Cloud](https://streamlit.io/cloud)
   from your own account, pointing at `state_app/app.py`.
2. In your app's **Settings → Secrets**, paste (see `.streamlit/secrets.toml.example`):
   ```
   SUPABASE_URL = "..."
   SUPABASE_ANON_KEY = "..."   # the ANON key only — never service_role
   STATE_CODE = "MH"           # your state's code, matches the `states` table
   ```
3. Ask the national admin to create your State admin login (Supabase Auth
   email/password) with `role='state'` and your `state_code` in
   `admin_profiles`.
4. Log in and start creating staff IDs.

## Local development

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # fill in real values
streamlit run app.py
```

## Pages
- **Manage Staff IDs** — create anonymous staff records, generate random login IDs
- **Generate Tests** — assign pre/post test instances
- **Take Test** — no-login screen for staff (enter ID only)
- **Questionnaire** — view default, upload translated CSV version
- **Export** — download this state's CSV data

## Security notes
- This app must only ever hold the **anon key**, never `service_role`.
- Row Level Security on the Supabase side enforces that this app's
  logged-in analyst can only see/write rows for their own `state_code`.
- The "Take Test" page intentionally has no login — it calls narrow
  SECURITY DEFINER database functions that do their own authorization
  check against the staff ID, so an anon key cannot read/write any table
  directly, only through those functions. See `supabase/schema.sql`.
