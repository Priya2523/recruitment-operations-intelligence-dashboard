# ================================================================
# RECRUITMENT INTELLIGENCE DASHBOARD


# ================================================================

print("=" * 70)
print("RECRUITMENT INTELLIGENCE DASHBOARD")
print("=" * 70)

import pandas as pd
import numpy as np
import gradio as gr
import matplotlib.pyplot as plt
import os
import re
from difflib import SequenceMatcher


# ============================================================
# 1. CONFIDENTIALITY / CLIENT MASKING
# ============================================================

CLIENT_MAP = {
    "Prowess": "Technology & Business Consulting",
    "Lodha Group": "Real Estate & Infrastructure",
    "Lodha": "Real Estate & Infrastructure",
    "Fischer Group": "Industrial & Engineering Solutions",
    "Fischer": "Industrial & Engineering Solutions",
    "L&T": "Engineering & Infrastructure",
    "Leviat": "Construction Products & Solutions",
    "Alumil": "Construction Products & Solutions",
    "Hilti India": "Building & Industrial Solutions",
    "Hilti": "Building & Industrial Solutions",
    "Lakshmi Hospital": "Healthcare & Hospital Services"
}


def mask_client(value):
    if pd.isna(value):
        return value
    text = str(value)
    for actual, masked in CLIENT_MAP.items():
        if actual.lower() in text.lower():
            return masked
    return text


def _empty_chart(message):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(
        0.5, 0.5, message,
        ha="center", va="center",
        fontsize=12, color="#6b7280", wrap=True
    )
    return fig


# ============================================================
# 2. COLUMN DETECTION — TOKEN-BOUNDARY MATCHING
# ============================================================

def _tokens(s):
    return set(str(s).strip().lower().replace(" ", "_").split("_"))


def detect_column(df, candidates, claimed=None):
    if df is None:
        return None
    if claimed is None:
        claimed = set()

    lookup = {str(c).strip().lower(): c for c in df.columns}

    for candidate in candidates:
        key = candidate.strip().lower()
        if key in lookup and lookup[key] not in claimed:
            return lookup[key]

    for column in df.columns:
        if column in claimed:
            continue
        col_tokens = _tokens(column)
        for candidate in candidates:
            cand_tokens = _tokens(candidate)
            if cand_tokens.issubset(col_tokens):
                return column

    return None


CANDIDATE_ALIASES = [
    "candidate_name", "candidate name", "full_name", "full name",
    "applicant_name", "applicant name"
]

ROLE_ALIASES = [
    "target_role", "target role", "candidate_previous_role", "position_applied",
    "position applied", "applied for", "applied_for", "job role", "job title",
    "job_title", "designation", "recruitment_role", "positions"
]

BUSINESS_ALIASES = [
    "confidential_client_business", "client_business", "business_group",
    "business group", "client company", "client_company", "company name",
    "company_name", "client name", "client_name"
]

MATCH_LEVEL_ALIASES = ["match_level", "match level"]
MATCH_SCORE_ALIASES = ["match_score", "match score"]
PRIORITY_ALIASES = ["priority_category", "priority category", "priority"]
RISK_LEVEL_ALIASES = ["joining_risk_level", "joining risk level", "risk_level"]
RISK_SCORE_ALIASES = ["joining_risk_score", "joining risk score", "risk_score"]
ACTION_ALIASES = ["combined_recruiter_action", "recommended_action", "recommended action"]

# Generic fallback aliases — used only when the pipeline columns above are missing
NOTICE_ALIASES = ["notice_period", "notice period", "notice"]
STATUS_ALIASES = ["status", "candidate_status", "application_status", "current_status"]


# ============================================================
# 3. GENERIC (NON-COMPANY-SPECIFIC) FALLBACK SCORING
# ============================================================

def generic_risk_score(row, notice_col, status_col):
    score = 0

    if status_col:
        status_text = str(row.get(status_col, "")).lower()
        if any(neg in status_text for neg in ["declined", "not interested", "withdrawn", "rejected"]):
            return 0, "LOW"
        if any(pos in status_text for pos in ["offer", "selected"]):
            score += 20

    if notice_col:
        notice_text = str(row.get(notice_col, "")).lower()
        digits = "".join(ch for ch in notice_text if ch.isdigit())
        if digits:
            days = int(digits[:3])
            if days >= 60:
                score += 40
            elif days >= 30:
                score += 20
        elif "immediate" in notice_text or notice_text.strip() == "0":
            score += 0
        elif notice_text.strip() in ("", "nan", "none"):
            score += 15

    if score >= 50:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    else:
        level = "LOW"

    return score, level


def generic_role_match(candidate_role, job_description):
    if not job_description or not candidate_role:
        return None, None

    a = str(candidate_role).lower().strip()
    b = str(job_description).lower().strip()

    ratio = SequenceMatcher(None, a, b).ratio()
    score = round(ratio * 100, 1)

    if score >= 60:
        level = "HIGH"
    elif score >= 35:
        level = "MEDIUM"
    elif score > 0:
        level = "LOW"
    else:
        level = "NO MATCH"

    return score, level


# ============================================================
# 4. LOAD FILE
# ============================================================

def load_uploaded_file(file):
    if file is None:
        return None, "Please upload a CSV or XLSX file."
    try:
        file_path = file.name
        extension = os.path.splitext(file_path)[1].lower()

        if extension == ".csv":
            df = pd.read_csv(file_path)
        elif extension in [".xlsx", ".xls"]:
            df = pd.read_excel(file_path)
        else:
            return None, "Unsupported file type. Please upload CSV or XLSX."

        df = df.dropna(how="all").copy()
        df.columns = [str(c).strip() for c in df.columns]

        if df.empty:
            return None, "The uploaded file is empty."

        return df, (
            f"File loaded successfully: "
            f"{len(df):,} records x {len(df.columns)} columns"
        )

    except Exception as e:
        return None, f"Unable to read file: {str(e)}"


# ============================================================
# 5. RECRUITMENT ANALYSIS
# ============================================================

def analyze_recruitment(file, job_description=None):

    df, message = load_uploaded_file(file)

    if df is None:
        blank_chart = _empty_chart(message)
        return (
            message,
            0, 0, 0, 0,
            0, 0, 0, 0,
            pd.DataFrame(),
            blank_chart,
            pd.DataFrame(),
            pd.DataFrame(),
            blank_chart,
            pd.DataFrame(),
            blank_chart,
            pd.DataFrame(),
            pd.DataFrame()
        )

    claimed_columns = set()

    candidate_col = detect_column(df, CANDIDATE_ALIASES, claimed_columns)
    if candidate_col:
        claimed_columns.add(candidate_col)

    role_col = detect_column(df, ROLE_ALIASES, claimed_columns)
    if role_col:
        claimed_columns.add(role_col)

    business_col = detect_column(df, BUSINESS_ALIASES, claimed_columns)
    if business_col:
        claimed_columns.add(business_col)

    match_level_col = detect_column(df, MATCH_LEVEL_ALIASES)
    priority_col = detect_column(df, PRIORITY_ALIASES)
    risk_level_col = detect_column(df, RISK_LEVEL_ALIASES)
    risk_score_col = detect_column(df, RISK_SCORE_ALIASES)
    action_col = detect_column(df, ACTION_ALIASES)

    # Generic fallback fields (only used if pipeline columns above are missing)
    notice_col = detect_column(df, NOTICE_ALIASES)
    status_col = detect_column(df, STATUS_ALIASES)

    # ========================================================
    # 6. BASIC KPIs
    # ========================================================

    total_records = len(df)

    unique_candidates = (
        df[candidate_col].dropna().astype(str).str.strip().nunique()
        if candidate_col else 0
    )

    unique_roles = (
        df[role_col].dropna().astype(str).str.strip().nunique()
        if role_col else 0
    )

    reusable_candidates = 0
    if candidate_col and role_col:
        temp = df[[candidate_col, role_col]].dropna()
        reusable_counts = temp.groupby(candidate_col)[role_col].nunique()
        reusable_candidates = (reusable_counts > 1).sum()

    # ========================================================
    # 7. MATCH ANALYSIS (pipeline column OR generic JD match)
    # ========================================================

    match_count = 0
    high_matches = 0
    high_priority_matches = 0
    high_risk_matches = 0

    match_summary = pd.DataFrame(columns=["Match Level", "Matches"])
    priority_summary = pd.DataFrame(columns=["Priority Category", "Matches"])
    risk_summary = pd.DataFrame(columns=["Joining Risk Level", "Candidate-Role Rows"])

    computed_match_levels = None

    if match_level_col:
        levels = df[match_level_col].fillna("NO MATCH").astype(str).str.upper().str.strip()
        match_count = len(df)
        match_summary = levels.value_counts().rename_axis("Match Level").reset_index(name="Matches")
        high_matches = (levels == "HIGH").sum()
    elif role_col and job_description:
        # GENERIC FALLBACK: score every candidate's role against the pasted JD
        computed = df[role_col].apply(lambda r: generic_role_match(r, job_description))
        computed_match_levels = computed.apply(lambda x: x[1] if x[1] else "NO MATCH")
        match_count = len(df)
        match_summary = computed_match_levels.value_counts().rename_axis("Match Level").reset_index(name="Matches")
        high_matches = (computed_match_levels == "HIGH").sum()

    # ========================================================
    # 8. PRIORITY ANALYSIS
    # ========================================================

    if priority_col:
        priorities = df[priority_col].fillna("P4 - LOW / NO PRIORITY").astype(str).str.upper().str.strip()
        priority_summary = priorities.value_counts().rename_axis("Priority Category").reset_index(name="Matches")
        high_priority_matches = priorities.str.contains("P1|P2|HIGH", case=False, regex=True).sum()

    # ========================================================
    # 9. JOINING-RISK ANALYSIS (pipeline column OR generic heuristic)
    # ========================================================

    if risk_level_col:
        risk_levels = df[risk_level_col].fillna("UNKNOWN").astype(str).str.upper().str.strip()
        risk_summary = risk_levels.value_counts().rename_axis("Joining Risk Level").reset_index(name="Candidate-Role Rows")
        high_risk_matches = (risk_levels == "HIGH").sum()
    elif notice_col or status_col:
        # GENERIC FALLBACK — computes risk from whatever raw fields exist
        computed = df.apply(lambda row: generic_risk_score(row, notice_col, status_col), axis=1)
        risk_levels = computed.apply(lambda x: x[1])
        risk_summary = risk_levels.value_counts().rename_axis("Joining Risk Level").reset_index(name="Candidate-Role Rows")
        high_risk_matches = (risk_levels == "HIGH").sum()

    # ========================================================
    # 10. BUSINESS GROUP ANALYSIS
    # ========================================================

    business_summary = pd.DataFrame(columns=["Business Group", "Candidate Records"])
    business_plot = None

    if business_col:
        business_data = df.copy()
        business_data["Business Group"] = business_data[business_col].apply(mask_client)
        business_summary = business_data["Business Group"].fillna("Not Available").value_counts().reset_index()
        business_summary.columns = ["Business Group", "Candidate Records"]

        chart_data = business_summary.head(10)
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.barh(chart_data["Business Group"][::-1], chart_data["Candidate Records"][::-1])
        ax.set_title("Recruitment by Business Group")
        ax.set_xlabel("Candidate Records")
        plt.tight_layout()
        business_plot = fig
    else:
        business_plot = _empty_chart("No client/business column found in this file.")

    # ========================================================
    # 11. TOP ROLES
    # ========================================================

    role_summary = pd.DataFrame(columns=["Role", "Candidate Records"])
    if role_col:
        role_summary = df[role_col].fillna("Unknown").astype(str).str.strip().value_counts().head(10).reset_index()
        role_summary.columns = ["Role", "Candidate Records"]

    # ========================================================
    # 12. MATCH QUALITY CHART
    # ========================================================

    match_plot = None
    if not match_summary.empty:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(match_summary["Match Level"], match_summary["Matches"])
        ax.set_title("Candidate-Role Match Quality")
        ax.set_ylabel("Matches")
        plt.xticks(rotation=20)
        plt.tight_layout()
        match_plot = fig
    else:
        match_plot = _empty_chart(
            "No match_level column found, and no Job Description provided.\n"
            "Paste a JD above to enable match scoring on this file."
        )

    # ========================================================
    # 13. JOINING-RISK CHART
    # ========================================================

    risk_plot = None
    if not risk_summary.empty:
        order = ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
        risk_summary["Joining Risk Level"] = pd.Categorical(risk_summary["Joining Risk Level"], categories=order, ordered=True)
        risk_summary = risk_summary.sort_values("Joining Risk Level")

        fig, ax = plt.subplots(figsize=(8, 5))
        colors = {"HIGH": "#dc2626", "MEDIUM": "#f59e0b", "LOW": "#16a34a", "UNKNOWN": "#94a3b8"}
        bar_colors = [colors.get(str(lvl), "#94a3b8") for lvl in risk_summary["Joining Risk Level"]]
        ax.bar(risk_summary["Joining Risk Level"].astype(str), risk_summary["Candidate-Role Rows"], color=bar_colors)
        ax.set_title("Joining-Risk Distribution")
        ax.set_ylabel("Candidate-Role Rows")
        plt.tight_layout()
        risk_plot = fig
    else:
        risk_plot = _empty_chart(
            "No joining_risk_level column, and no notice-period/status field found\n"
            "in this file to compute risk from."
        )

    # ========================================================
    # 14. CANDIDATE RECOMMENDATIONS
    # ========================================================

    match_score_col = detect_column(df, MATCH_SCORE_ALIASES)

    rec_column_map = []
    if candidate_col:
        rec_column_map.append((candidate_col, "Candidate"))
    if role_col:
        rec_column_map.append((role_col, "Target Role"))
    if match_score_col:
        rec_column_map.append((match_score_col, "Match Score"))
    if match_level_col:
        rec_column_map.append((match_level_col, "Match Level"))
    if risk_score_col:
        rec_column_map.append((risk_score_col, "Joining Risk Score"))
    if risk_level_col:
        rec_column_map.append((risk_level_col, "Joining Risk Level"))
    if priority_col:
        rec_column_map.append((priority_col, "Priority"))
    if action_col:
        rec_column_map.append((action_col, "Recommended Action"))

    seen_cols = set()
    rec_column_map = [
        pair for pair in rec_column_map
        if not (pair[0] in seen_cols or seen_cols.add(pair[0]))
    ]

    if rec_column_map:
        source_cols = [c for c, _ in rec_column_map]
        recommendations = df[source_cols].copy()
        recommendations.columns = [name for _, name in rec_column_map]

        sort_cols = [c for c in ["Match Score", "Joining Risk Score"] if c in recommendations.columns]
        if sort_cols:
            for c in sort_cols:
                recommendations[c] = pd.to_numeric(recommendations[c], errors="coerce")
            recommendations = recommendations.sort_values(sort_cols, ascending=False, na_position="last")

        recommendations = recommendations.head(50)
    elif candidate_col and computed_match_levels is not None:
        # GENERIC FALLBACK recommendation table, built from the JD match
        recommendations = pd.DataFrame({
            "Candidate": df[candidate_col],
            "Target Role": df[role_col] if role_col else "Unknown",
            "Match Level (vs pasted JD)": computed_match_levels
        }).sort_values("Match Level (vs pasted JD)", ascending=False).head(50)
    else:
        recommendations = pd.DataFrame({
            "Message": ["Candidate recommendation fields were not found in the uploaded file."]
        })

    # ========================================================
    # 15. STATUS MESSAGE
    # ========================================================

    detected = []
    missing_notes = []

    if candidate_col:
        detected.append("Candidate")
    else:
        missing_notes.append("No candidate-name column found -> candidate counts will show 0.")

    if role_col:
        detected.append("Role")
    else:
        missing_notes.append("No role/position column found -> Unique Roles, Top Roles and Reusable Candidates will show 0/empty.")

    if business_col:
        detected.append("Business")
    else:
        missing_notes.append("No client/business column found -> Business Group section will be empty.")

    if match_level_col:
        detected.append("Match")
    elif job_description and role_col:
        detected.append("Match (computed from pasted JD)")
    else:
        missing_notes.append("No match_level column found and no JD pasted -> Match Quality will be empty. Paste a Job Description above to enable it.")

    if priority_col:
        detected.append("Priority")
    else:
        missing_notes.append("No priority_category column found -> Recruiter Prioritization will be empty.")

    if risk_level_col:
        detected.append("Joining Risk")
    elif notice_col or status_col:
        detected.append("Joining Risk (computed from notice/status fields)")
    else:
        missing_notes.append("No joining_risk_level column and no notice-period/status field found -> Joining-Risk Overview will be empty.")

    status_lines = [
        "Analysis completed successfully.",
        "",
        f"Records processed: {total_records:,}",
        f"Columns detected: {', '.join(detected) if detected else 'Basic dataset only'}",
    ]

    if missing_notes:
        status_lines.append("")
        status_lines.append("Notes on this file (not errors -- just what could not be found):")
        for note in missing_notes:
            status_lines.append(f"- {note}")

    status_message = "\n".join(status_lines)

    return (
        status_message,
        total_records, unique_candidates, unique_roles, reusable_candidates,
        match_count, high_matches, high_priority_matches, high_risk_matches,
        business_summary, business_plot,
        role_summary,
        match_summary, match_plot,
        risk_summary, risk_plot,
        priority_summary,
        recommendations
    )


# ============================================================
# 16. GRADIO UI
# ============================================================

with gr.Blocks(title="Recruitment Intelligence Dashboard", theme=gr.themes.Soft()) as demo:

    gr.Markdown("""
    # Recruitment Intelligence Dashboard

    **Analyze recruitment data, candidate-role matching, recruiter priorities
    and joining-risk from an uploaded CSV or XLSX file.**

    Works on files already processed by the full pipeline, and on
    brand-new recruiter trackers it has never seen before.
    """)

    with gr.Row():
        file_input = gr.File(label="Upload Recruitment Data", file_types=[".csv", ".xlsx", ".xls"], type="filepath")
        jd_input = gr.Textbox(
            label="Job Description (optional — enables Match scoring on unseen files)",
            lines=3,
            placeholder="Paste the role/JD here to score candidates against it..."
        )

    analyze_button = gr.Button("Analyze Recruitment Data", variant="primary")

    status_box = gr.Markdown("Upload a recruitment CSV/XLSX file and click **Analyze Recruitment Data**.")

    gr.Markdown("## Recruitment Overview")
    with gr.Row():
        kpi1 = gr.Number(label="Recruitment Records", value=0, interactive=False)
        kpi2 = gr.Number(label="Unique Candidates", value=0, interactive=False)
        kpi3 = gr.Number(label="Unique Roles", value=0, interactive=False)
        kpi4 = gr.Number(label="Reusable Candidates", value=0, interactive=False)

    gr.Markdown("## Candidate-Role Matching")
    with gr.Row():
        kpi5 = gr.Number(label="Candidate-Role Matches", value=0, interactive=False)
        kpi6 = gr.Number(label="HIGH Matches", value=0, interactive=False)
        kpi7 = gr.Number(label="High-Priority Matches", value=0, interactive=False)
        kpi8 = gr.Number(label="High Joining-Risk Rows", value=0, interactive=False)

    gr.Markdown("## Recruitment by Business Group")
    business_table = gr.Dataframe(headers=["Business Group", "Candidate Records"], interactive=False)
    business_plot_component = gr.Plot()

    gr.Markdown("## Top Recruitment Roles")
    role_table = gr.Dataframe(headers=["Role", "Candidate Records"], interactive=False)

    gr.Markdown("## Match Quality")
    match_table = gr.Dataframe(headers=["Match Level", "Matches"], interactive=False)
    match_plot_component = gr.Plot()

    gr.Markdown("## Joining-Risk Overview")
    risk_table = gr.Dataframe(headers=["Joining Risk Level", "Candidate-Role Rows"], interactive=False)
    risk_plot_component = gr.Plot()

    gr.Markdown("## Recruiter Prioritization")
    priority_table = gr.Dataframe(headers=["Priority Category", "Matches"], interactive=False)

    gr.Markdown("## Top Candidate Recommendations")
    recommendation_table = gr.Dataframe(interactive=False)

    analyze_button.click(
        fn=analyze_recruitment,
        inputs=[file_input, jd_input],
        outputs=[
            status_box,
            kpi1, kpi2, kpi3, kpi4,
            kpi5, kpi6, kpi7, kpi8,
            business_table, business_plot_component,
            role_table,
            match_table, match_plot_component,
            risk_table, risk_plot_component,
            priority_table,
            recommendation_table
        ]
    )

print("\nLaunching Recruitment Intelligence Dashboard...")
demo.launch()
