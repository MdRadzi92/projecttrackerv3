import streamlit as st
import pandas as pd
from datetime import date, timedelta
import os
from io import BytesIO
from github import Github
import streamlit.components.v1 as components

# PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

APP_TITLE = "Project Tracker Pro"
EXCEL_FILE = "projects.xlsx"
SHEET_NAME = "Projects"
LOGO_PATH = "assets/logo.png"

# -----------------------------
# Helpers: Auth & Secrets
# -----------------------------
def load_users_from_secrets():
    users = {}
    try:
        users_section = st.secrets.get("users", {})
        for username, cfg in users_section.items():
            users[username] = {"password": cfg.get("password", ""), "role": cfg.get("role", "viewer")}
    except Exception:
        pass
    return users

USERS = load_users_from_secrets()
# Fallback for local quick testing
if not USERS:
    USERS = {
        "admin": {"password": "admin", "role": "admin"},
        "viewer": {"password": "viewer", "role": "viewer"},
    }

def login_ui():
    st.sidebar.markdown("### 🔐 Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Sign in"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state["auth_user"] = username
            st.session_state["auth_role"] = USERS[username]["role"]
            st.experimental_rerun()
        else:
            st.sidebar.error("Invalid username or password")
    st.sidebar.caption("Default test: admin/admin, viewer/viewer")

def is_admin():
    return st.session_state.get("auth_role") == "admin"

def current_user():
    return st.session_state.get("auth_user", "")

# -----------------------------
# Data IO
# -----------------------------
def ensure_excel():
    if not os.path.exists(EXCEL_FILE):
        df = pd.DataFrame(columns=["Year","Project Code","Project Name","Location","Project Start","Project End","Project Team"])
        df.to_excel(EXCEL_FILE, sheet_name=SHEET_NAME, index=False)

def load_data():
    ensure_excel()
    return pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)

def save_data(df: pd.DataFrame):
    df.to_excel(EXCEL_FILE, sheet_name=SHEET_NAME, index=False)

# -----------------------------
# GitHub commit
# -----------------------------
def can_commit_to_github():
    return "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets

def commit_excel_to_github(message="Update projects.xlsx"):
    try:
        if not can_commit_to_github():
            st.info("ℹ️ GitHub secrets not configured; skipping commit.")
            return
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["GITHUB_REPO"]
        branch = st.secrets.get("GITHUB_BRANCH", "main")
        g = Github(token)
        repo = g.get_repo(repo_name)

        with open(EXCEL_FILE, "rb") as f:
            content_bytes = f.read()

        try:
            remote = repo.get_contents(EXCEL_FILE, ref=branch)
            repo.update_file(remote.path, message, content_bytes, remote.sha, branch=branch)
        except Exception:
            repo.create_file(EXCEL_FILE, "Create projects.xlsx", content_bytes, branch=branch)
        st.success("📤 Changes pushed to GitHub.")
    except Exception as e:
        st.error(f"GitHub commit failed: {e}")

# -----------------------------
# ICS (Calendar) helpers
# -----------------------------
def date_to_ics(d):
    # all-day event date format YYYYMMDD
    return pd.to_datetime(d).strftime("%Y%m%d")

def make_ics_for_row(row):
    start = date_to_ics(row["Project Start"])
    # DTEND in all-day should be day after end date
    end_plus = pd.to_datetime(row["Project End"]) + timedelta(days=1)
    end = end_plus.strftime("%Y%m%d")
    summary = f"{row['Project Code']} - {row['Project Name']}"
    location = str(row.get("Location", ""))

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Project Tracker Pro//EN
BEGIN:VEVENT
UID:{row['Project Code']}@project-tracker
DTSTAMP:{pd.Timestamp.utcnow().strftime('%Y%m%dT%H%M%SZ')}
DTSTART;VALUE=DATE:{start}
DTEND;VALUE=DATE:{end}
SUMMARY:{summary}
LOCATION:{location}
DESCRIPTION:Team: {row.get('Project Team','')}
END:VEVENT
END:VCALENDAR
"""
    return ics.encode("utf-8")

def make_ics_for_dataframe(df):
    ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Project Tracker Pro//EN\n"
    for _, r in df.iterrows():
        ics += "BEGIN:VEVENT\n"
        ics += f"UID:{r['Project Code']}@project-tracker\n"
        ics += f"DTSTAMP:{pd.Timestamp.utcnow().strftime('%Y%m%dT%H%M%SZ')}\n"
        ics += f"DTSTART;VALUE=DATE:{date_to_ics(r['Project Start'])}\n"
        end_plus = pd.to_datetime(r["Project End"]) + timedelta(days=1)
        ics += f"DTEND;VALUE=DATE:{end_plus.strftime('%Y%m%d')}\n"
        ics += f"SUMMARY:{r['Project Code']} - {r['Project Name']}\n"
        ics += f"LOCATION:{str(r.get('Location',''))}\n"
        ics += f"DESCRIPTION:Team: {str(r.get('Project Team',''))}\n"
        ics += "END:VEVENT\n"
    ics += "END:VCALENDAR\n"
    return ics.encode("utf-8")

# -----------------------------
# PDF helpers
# -----------------------------
def make_pdf_from_dataframe(df, title="Project Report"):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    elements = []
    elements.append(Paragraph(f"<b>{title}</b>", styles['Title']))
    elements.append(Spacer(1, 12))

    if len(df) == 0:
        elements.append(Paragraph("No data.", styles['Normal']))
    else:
        cols = ["Year","Project Code","Project Name","Location","Project Start","Project End","Project Team"]
        data = [cols] + df[cols].astype(str).values.tolist()
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4CAF50')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.lightgrey]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ]))
        elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer

# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Project Tracker Pro", page_icon="📊", layout="wide")

# Header with logo + title
col_logo, col_title = st.columns([1,8])
with col_logo:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=64)
with col_title:
    st.markdown(f"### **{APP_TITLE}**")

# Auth gate
if "auth_user" not in st.session_state:
    login_ui()
    st.stop()
else:
    st.sidebar.success(f"Logged in as: {current_user()} ({st.session_state.get('auth_role')})")
    if st.sidebar.button("Sign out"):
        st.session_state.clear()
        st.experimental_rerun()

df = load_data()

# Filters
with st.sidebar:
    st.markdown("### 🔎 Filters")
    years = ["All"] + sorted([y for y in df["Year"].dropna().unique().tolist()])
    year_filter = st.selectbox("Year", years)
    locations = ["All"] + sorted([l for l in df["Location"].dropna().unique().tolist()])
    location_filter = st.selectbox("Location", locations)
    code_query = st.text_input("Search code/name/location")

filtered = df.copy()
if year_filter != "All":
    filtered = filtered[filtered["Year"] == (int(year_filter) if isinstance(year_filter, str) and year_filter.isdigit() else year_filter)]
if location_filter != "All":
    filtered = filtered[filtered["Location"] == location_filter]
if code_query:
    q = code_query.lower()
    filtered = filtered[
        filtered["Project Code"].fillna("").str.lower().str.contains(q)
        | filtered["Project Name"].fillna("").str.lower().str.contains(q)
        | filtered["Location"].fillna("").str.lower().str.contains(q)
    ]

st.subheader("📋 Project List")
st.dataframe(filtered, use_container_width=True)

# Print / Export / Calendar
with st.expander("🖨️ Print / Export / Calendar"):
    # Print dialog
    if st.button("Open Print Dialog"):
        components.html("<script>window.print();</script>", height=0)

    # Download filtered Excel
    buf_xls = BytesIO()
    filtered.to_excel(buf_xls, index=False)
    buf_xls.seek(0)
    st.download_button("📥 Download filtered Excel", data=buf_xls, file_name="projects_filtered.xlsx")

    # Export filtered to PDF
    pdf_buf = make_pdf_from_dataframe(filtered, title="Project Tracker – Filtered Report")
    st.download_button("🧾 Export filtered to PDF", data=pdf_buf, file_name="projects_filtered.pdf", mime="application/pdf")

    # Calendar: select a row to generate ICS
    if len(filtered) > 0:
        idxs = list(filtered.index)
        sel = st.selectbox("Select a row for calendar (.ics)", options=idxs, format_func=lambda i: f"{filtered.loc[i,'Project Code']} – {filtered.loc[i,'Project Name']}")
        ics_single = make_ics_for_row(df.loc[sel])
        st.download_button("📅 Download .ics for selected project", data=ics_single, file_name=f"{df.loc[sel,'Project Code']}.ics", mime="text/calendar", key="dl_single_ics")

        # Bulk ICS for filtered
        bulk_ics = make_ics_for_dataframe(filtered)
        st.download_button("📅 Download .ics (all filtered)", data=bulk_ics, file_name="projects_filtered.ics", mime="text/calendar", key="dl_bulk_ics")

# -----------------------------
# Add Project (Admin only)
# -----------------------------
st.markdown("---")
st.subheader("➕ Add New Project")
if is_admin():
    with st.form("add_project_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            year = st.number_input("Year", min_value=2000, max_value=2100, value=date.today().year)
            code = st.text_input("Project Code")
        with col2:
            name = st.text_input("Project Name")
            location = st.text_input("Location")
        with col3:
            start = st.date_input("Project Start")
            end = st.date_input("Project End")
        team = st.text_area("Project Team (comma-separated usernames)")

        submitted = st.form_submit_button("Add Project")
        if submitted:
            new_row = {
                "Year": int(year),
                "Project Code": code.strip(),
                "Project Name": name.strip(),
                "Location": location.strip(),
                "Project Start": start,
                "Project End": end,
                "Project Team": team.strip(),
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(df)
            commit_excel_to_github("Add project")
            st.success("✅ Project added.")
            st.experimental_rerun()
else:
    st.info("Only Top Management (admin) can add new projects.")

# -----------------------------
# Edit / Delete (Admin OR Assigned in Project Team)
# -----------------------------
st.markdown("---")
st.subheader("✏️ Edit / Delete Project")

if len(df) == 0:
    st.info("No projects to edit yet.")
else:
    row_idx = st.number_input("Select row index to edit (0-based)", min_value=0, max_value=len(df)-1, step=1)
    row_team = str(df.loc[row_idx, "Project Team"] or "").lower()
    user = current_user().lower()
    can_edit = is_admin() or (user and user in [u.strip().lower() for u in row_team.split(",") if u.strip()])

    if not can_edit:
        st.warning("You are not authorized to edit this project. Ask admin to add your username into 'Project Team'.")
    else:
        with st.form("edit_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                year_e = st.number_input("Year", 2000, 2100, int(df.loc[row_idx, "Year"]) if not pd.isna(df.loc[row_idx, "Year"]) else date.today().year)
                code_e = st.text_input("Project Code", str(df.loc[row_idx, "Project Code"] or ""))
            with col2:
                name_e = st.text_input("Project Name", str(df.loc[row_idx, "Project Name"] or ""))
                location_e = st.text_input("Location", str(df.loc[row_idx, "Location"] or ""))
            with col3:
                start_e = st.date_input("Project Start", pd.to_datetime(df.loc[row_idx, "Project Start"]).date() if not pd.isna(df.loc[row_idx, "Project Start"]) else date.today())
                end_e = st.date_input("Project End", pd.to_datetime(df.loc[row_idx, "Project End"]).date() if not pd.isna(df.loc[row_idx, "Project End"]) else date.today())
            team_e = st.text_area("Project Team (comma-separated usernames)", str(df.loc[row_idx, "Project Team"] or ""))

            c1, c2 = st.columns(2)
            do_update = c1.form_submit_button("💾 Update Project")
            do_delete = c2.form_submit_button("🗑️ Delete Project")

        if do_update:
            df.loc[row_idx, "Year"] = int(year_e)
            df.loc[row_idx, "Project Code"] = code_e.strip()
            df.loc[row_idx, "Project Name"] = name_e.strip()
            df.loc[row_idx, "Location"] = location_e.strip()
            df.loc[row_idx, "Project Start"] = start_e
            df.loc[row_idx, "Project End"] = end_e
            df.loc[row_idx, "Project Team"] = team_e.strip()
            save_data(df)
            commit_excel_to_github("Edit project")
            st.success("✅ Updated.")
            st.experimental_rerun()

        if do_delete:
            df = df.drop(index=row_idx).reset_index(drop=True)
            save_data(df)
            commit_excel_to_github("Delete project")
            st.success("🗑️ Deleted.")
            st.experimental_rerun()
