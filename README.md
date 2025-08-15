# Project Tracker Pro (Streamlit + Excel)

**Features**
- Role-based login (admin vs viewer)
- Only admin can add; edit/delete allowed for admin or users listed in **Project Team**
- Auto-save to Excel + auto-commit to GitHub (when secrets configured)
- Filters + search
- Print dialog
- Export filtered **Excel** and **PDF**
- Add to Calendar: download **.ics** for one project or all filtered
- Company logo shown beside header (place at `assets/logo.png`)

## Run locally
```bash
pip install -r requirements.txt
streamlit run main.py
```
Default test users:
- `admin / admin` (admin)
- `viewer / viewer` (viewer)

## Deploy on Streamlit Community Cloud
1. Push this folder to a **public GitHub repo**.
2. Go to https://share.streamlit.io → New app.
3. Set **Main file path** to `main.py` → Deploy.

## Configure Secrets (for Cloud)
In **App → Settings → Secrets**:
```toml
# GitHub commit settings
GITHUB_TOKEN = "ghp_xxx"            # Personal Access Token with 'repo' scope
GITHUB_REPO = "yourname/project-tracker"
GITHUB_BRANCH = "main"              # optional

# Users & roles
[users.admin]
password = "strong_admin_password"
role = "admin"

[users.pm_ali]
password = "choose_a_password"
role = "viewer"
```

## Data columns
`Year | Project Code | Project Name | Location | Project Start | Project End | Project Team`

---
Made for MR RADZI. 🚀
