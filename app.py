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
    fig, ax = plt.subplots(figsize=(7, 4.5))
    fig.patch.set_alpha(0)
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
# 5. VISUAL STYLE HELPERS (colors, KPI cards, donut charts, badges)
# ============================================================

MATCH_COLORS = {"HIGH": "#16a34a", "MEDIUM": "#3b82f6", "LOW": "#f59e0b", "NO MATCH": "#9ca3af"}
RISK_COLORS = {"HIGH": "#dc2626", "MEDIUM": "#f59e0b", "LOW": "#16a34a", "UNKNOWN": "#9ca3af"}
PRIORITY_COLORS = {
    "P1 - IMMEDIATE REVIEW": "#dc2626",
    "P2 - HIGH PRIORITY": "#f59e0b",
    "P3 - REVIEW": "#3b82f6",
    "P4 - LOW / NO PRIORITY": "#9ca3af",
}
DONUT_PALETTE = ["#4f46e5", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#94a3b8"]

BADGE_COLORS = {
    "HIGH": ("#b91c1c", "#fee2e2"),
    "MEDIUM": ("#b45309", "#fef3c7"),
    "LOW": ("#15803d", "#dcfce7"),
    "NO MATCH": ("#4b5563", "#f3f4f6"),
    "UNKNOWN": ("#4b5563", "#f3f4f6"),
    "P1 - IMMEDIATE REVIEW": ("#b91c1c", "#fee2e2"),
    "P2 - HIGH PRIORITY": ("#b45309", "#fef3c7"),
    "P3 - REVIEW": ("#1d4ed8", "#dbeafe"),
    "P4 - LOW / NO PRIORITY": ("#4b5563", "#f3f4f6"),
}


def make_badge(value):
    if pd.isna(value) or str(value).strip() == "":
        return ""
    key = str(value).upper().strip()
    fg, bg = BADGE_COLORS.get(key, ("#374151", "#f3f4f6"))
    return (
        f'<span style="background:{bg};color:{fg};padding:3px 10px;'
        f'border-radius:999px;font-weight:600;font-size:12px;white-space:nowrap;">'
        f'{value}</span>'
    )


def kpi_card(label, value, color):
    return f"""
    <div style="background:white;border-radius:14px;padding:16px 18px;
                box-shadow:0 1px 4px rgba(0,0,0,0.08);border-top:4px solid {color};
                flex:1;min-width:150px;">
      <div style="font-size:12px;color:#6b7280;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.04em;">{label}</div>
      <div style="font-size:26px;font-weight:800;color:#111827;margin-top:6px;">{value}</div>
    </div>
    """


def kpi_grid(cards):
    return f'<div style="display:flex;gap:14px;flex-wrap:wrap;margin:6px 0 18px 0;">{"".join(cards)}</div>'


def insight_box(text):
    if not text:
        return ""
    return f"""
    <div style="background:#eef2ff;border-left:4px solid #4f46e5;border-radius:8px;
                padding:12px 16px;margin:10px 0 4px 0;color:#312e81;font-size:14px;line-height:1.5;">
      {text}
    </div>
    """


def donut_chart(labels, values, title, color_map=None):
    if not values or sum(values) == 0:
        return _empty_chart(f"No data available for {title}.")

    if color_map:
        colors = [color_map.get(str(l).upper().strip(), DONUT_PALETTE[i % len(DONUT_PALETTE)])
                  for i, l in enumerate(labels)]
    else:
        colors = [DONUT_PALETTE[i % len(DONUT_PALETTE)] for i in range(len(labels))]

    total = sum(values)
    fig, ax = plt.subplots(figsize=(6, 6))
    fig.patch.set_alpha(0)
    wedges, _texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct=lambda p: f"{p:.0f}%" if p >= 4 else "",
        startangle=90,
        colors=colors,
        pctdistance=0.78,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    )
    plt.setp(autotexts, size=11, weight="bold", color="white")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=14)
    ax.text(0, 0, f"{total:,}\ntotal", ha="center", va="center", fontsize=13, fontweight="bold", color="#111827")
    ax.legend(
        wedges, [f"{l} ({v:,})" for l, v in zip(labels, values)],
        loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2, frameon=False, fontsize=9
    )
    plt.tight_layout()
    return fig


# ============================================================
# 6. RECRUITMENT ANALYSIS
# ============================================================

def analyze_recruitment(file, job_description=None):

    df, message = load_uploaded_file(file)

    if df is None:
        blank_chart = _empty_chart(message)
        empty_reco = gr.update(value=pd.DataFrame(), datatype=None)
        return (
            message,
            kpi_grid([kpi_card(l, 0, c) for l, c in [
                ("Recruitment Records", "#4f46e5"), ("Unique Candidates", "#4f46e5"),
                ("Unique Roles", "#4f46e5"), ("Reusable Candidates", "#10b981")]]),
            kpi_grid([kpi_card(l, 0, c) for l, c in [
                ("Candidate-Role Matches", "#4f46e5"), ("HIGH Matches", "#10b981"),
                ("High-Priority Matches", "#f59e0b"), ("High Joining-Risk Rows", "#dc2626")]]),
            pd.DataFrame(), blank_chart, blank_chart, "",
            pd.DataFrame(), "",
            pd.DataFrame(), blank_chart, "",
            pd.DataFrame(), blank_chart, "",
            pd.DataFrame(), blank_chart, "",
            empty_reco,
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
    # BASIC KPIs
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
        reusable_candidates = int((reusable_counts > 1).sum())

    # ========================================================
    # MATCH ANALYSIS (pipeline column OR generic JD match)
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
        high_matches = int((levels == "HIGH").sum())
    elif role_col and job_description:
        computed = df[role_col].apply(lambda r: generic_role_match(r, job_description))
        computed_match_levels = computed.apply(lambda x: x[1] if x[1] else "NO MATCH")
        match_count = len(df)
        match_summary = computed_match_levels.value_counts().rename_axis("Match Level").reset_index(name="Matches")
        high_matches = int((computed_match_levels == "HIGH").sum())

    # ========================================================
    # PRIORITY ANALYSIS
    # ========================================================

    if priority_col:
        priorities = df[priority_col].fillna("P4 - LOW / NO PRIORITY").astype(str).str.upper().str.strip()
        priority_summary = priorities.value_counts().rename_axis("Priority Category").reset_index(name="Matches")
        high_priority_matches = int(priorities.str.contains("P1|P2|HIGH", case=False, regex=True).sum())

    # ========================================================
    # JOINING-RISK ANALYSIS (pipeline column OR generic heuristic)
    # ========================================================

    if risk_level_col:
        risk_levels = df[risk_level_col].fillna("UNKNOWN").astype(str).str.upper().str.strip()
        risk_summary = risk_levels.value_counts().rename_axis("Joining Risk Level").reset_index(name="Candidate-Role Rows")
        high_risk_matches = int((risk_levels == "HIGH").sum())
    elif notice_col or status_col:
        computed = df.apply(lambda row: generic_risk_score(row, notice_col, status_col), axis=1)
        risk_levels = computed.apply(lambda x: x[1])
        risk_summary = risk_levels.value_counts().rename_axis("Joining Risk Level").reset_index(name="Candidate-Role Rows")
        high_risk_matches = int((risk_levels == "HIGH").sum())

    # ========================================================
    # BUSINESS GROUP ANALYSIS
    # ========================================================

    business_summary = pd.DataFrame(columns=["Business Group", "Candidate Records"])
    business_bar = None
    business_donut = None
    business_insight = ""

    if business_col:
        business_data = df.copy()
        business_data["Business Group"] = business_data[business_col].apply(mask_client)
        business_summary = business_data["Business Group"].fillna("Not Available").value_counts().reset_index()
        business_summary.columns = ["Business Group", "Candidate Records"]

        chart_data = business_summary.head(10)
        fig, ax = plt.subplots(figsize=(9, 5))
        fig.patch.set_alpha(0)
        bars = ax.barh(chart_data["Business Group"][::-1], chart_data["Candidate Records"][::-1], color="#4f46e5")
        ax.set_title("Recruitment by Business Group (ranked)", fontsize=13, fontweight="bold")
        ax.set_xlabel("Candidate Records")
        ax.spines[["top", "right"]].set_visible(False)
        for bar in bars:
            ax.text(bar.get_width() + max(chart_data["Candidate Records"]) * 0.01,
                    bar.get_y() + bar.get_height() / 2,
                    f"{int(bar.get_width()):,}", va="center", fontsize=9, color="#374151")
        plt.tight_layout()
        business_bar = fig

        # Donut: top 5 groups + "Other"
        top5 = business_summary.head(5).copy()
        other_total = business_summary["Candidate Records"].iloc[5:].sum()
        labels = top5["Business Group"].tolist()
        values = top5["Candidate Records"].tolist()
        if other_total > 0:
            labels.append("Other")
            values.append(int(other_total))
        business_donut = donut_chart(labels, values, "Share of Recruitment by Business Group")

        top_row = business_summary.iloc[0]
        total_biz = business_summary["Candidate Records"].sum()
        pct = top_row["Candidate Records"] / total_biz * 100 if total_biz else 0
        business_insight = insight_box(
            f"📌 <b>{top_row['Business Group']}</b> drives <b>{pct:.0f}%</b> of all recruitment activity "
            f"({top_row['Candidate Records']:,} of {total_biz:,} records) — the single biggest hiring demand center."
        )
    else:
        business_bar = _empty_chart("No client/business column found in this file.")
        business_donut = _empty_chart("No client/business column found in this file.")

    # ========================================================
    # TOP ROLES
    # ========================================================

    role_summary = pd.DataFrame(columns=["Role", "Candidate Records"])
    role_insight = ""
    if role_col:
        role_summary = df[role_col].fillna("Unknown").astype(str).str.strip().value_counts().head(10).reset_index()
        role_summary.columns = ["Role", "Candidate Records"]
        if not role_summary.empty:
            role_insight = insight_box(
                f"📌 The role <b>{role_summary.iloc[0]['Role']}</b> has the highest recruitment activity "
                f"with <b>{role_summary.iloc[0]['Candidate Records']:,}</b> candidate records — "
                f"a good indicator of where hiring pressure is greatest right now."
            )

    # ========================================================
    # MATCH QUALITY DONUT
    # ========================================================

    match_donut = None
    match_insight = ""
    if not match_summary.empty:
        match_donut = donut_chart(
            match_summary["Match Level"].tolist(),
            match_summary["Matches"].tolist(),
            "Candidate-Role Match Quality",
            color_map=MATCH_COLORS,
        )
        total_m = match_summary["Matches"].sum()
        pct_high = high_matches / total_m * 100 if total_m else 0
        no_match_row = match_summary[match_summary["Match Level"] == "NO MATCH"]
        no_match_count = int(no_match_row["Matches"].sum())
        pct_no_match = no_match_count / total_m * 100 if total_m else 0

        insight_lines = [
            f"📌 Only <b>{pct_high:.1f}%</b> of candidate-role pairs are <b>HIGH</b>-quality matches "
            f"({high_matches:,} of {total_m:,}). Recruiters should prioritize outreach on these first "
            f"before working through MEDIUM/LOW matches."
        ]
        if no_match_count and pct_no_match >= 30:
            insight_lines.append(
                f"📌 <b>{pct_no_match:.0f}%</b> of records ({no_match_count:,}) show <b>NO MATCH</b> to the "
                f"target role — this points to a sourcing/tagging gap (candidates not yet mapped to a role), "
                f"not a candidate-quality problem."
            )
        match_insight = "".join(insight_box(line) for line in insight_lines)
    else:
        match_donut = _empty_chart(
            "No match_level column found, and no Job Description provided.\n"
            "Paste a JD above to enable match scoring on this file."
        )

    # ========================================================
    # JOINING-RISK DONUT
    # ========================================================

    risk_donut = None
    risk_insight = ""
    if not risk_summary.empty:
        order = ["HIGH", "MEDIUM", "LOW", "UNKNOWN"]
        risk_summary["Joining Risk Level"] = pd.Categorical(risk_summary["Joining Risk Level"], categories=order, ordered=True)
        risk_summary = risk_summary.sort_values("Joining Risk Level")
        risk_summary["Joining Risk Level"] = risk_summary["Joining Risk Level"].astype(str)

        risk_donut = donut_chart(
            risk_summary["Joining Risk Level"].tolist(),
            risk_summary["Candidate-Role Rows"].tolist(),
            "Joining-Risk Distribution",
            color_map=RISK_COLORS,
        )
        total_r = risk_summary["Candidate-Role Rows"].sum()
        pct_high_risk = high_risk_matches / total_r * 100 if total_r else 0
        risk_insight = insight_box(
            f"📌 <b>{pct_high_risk:.1f}%</b> of candidates ({high_risk_matches:,} of {total_r:,}) fall into "
            f"<b>HIGH</b> joining-risk. Proactive follow-up with this group reduces last-minute drop-offs "
            f"before joining date."
        )
    else:
        risk_donut = _empty_chart(
            "No joining_risk_level column, and no notice-period/status field found\n"
            "in this file to compute risk from."
        )

    # ========================================================
    # PRIORITY DONUT
    # ========================================================

    priority_donut = None
    priority_insight = ""
    if not priority_summary.empty:
        priority_donut = donut_chart(
            priority_summary["Priority Category"].tolist(),
            priority_summary["Matches"].tolist(),
            "Recruiter Priority Split",
            color_map=PRIORITY_COLORS,
        )
        total_p = priority_summary["Matches"].sum()
        p1_row = priority_summary[priority_summary["Priority Category"].str.contains("P1", na=False)]
        p1_count = int(p1_row["Matches"].sum())
        pct_p1 = p1_count / total_p * 100 if total_p else 0
        priority_insight = insight_box(
            f"📌 <b>{p1_count:,} candidates ({pct_p1:.1f}%)</b> are flagged <b>P1 - Immediate Review</b>. "
            f"Clearing this queue first prevents strong candidates from going cold while waiting on recruiters."
        )
    else:
        priority_donut = _empty_chart("No priority_category column found in this file.")

    # ========================================================
    # CANDIDATE RECOMMENDATIONS
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

    badge_columns = {"Match Level", "Joining Risk Level", "Priority"}

    if rec_column_map:
        source_cols = [c for c, _ in rec_column_map]
        recommendations = df[source_cols].copy()
        recommendations.columns = [name for _, name in rec_column_map]

        sort_cols = [c for c in ["Match Score", "Joining Risk Score"] if c in recommendations.columns]
        if sort_cols:
            for c in sort_cols:
                recommendations[c] = pd.to_numeric(recommendations[c], errors="coerce")
            recommendations = recommendations.sort_values(sort_cols, ascending=False, na_position="last")

        recommendations = recommendations.head(50).reset_index(drop=True)

        if "Recommended Action" in recommendations.columns:
            recommendations["Recommended Action"] = (
                recommendations["Recommended Action"]
                .astype(str)
                .apply(lambda t: t if len(t) <= 55 else t[:52].rstrip() + "...")
            )

        datatype = []
        for col in recommendations.columns:
            if col in badge_columns:
                recommendations[col] = recommendations[col].apply(make_badge)
                datatype.append("markdown")
            else:
                datatype.append("number" if pd.api.types.is_numeric_dtype(recommendations[col]) else "str")

    elif candidate_col and computed_match_levels is not None:
        recommendations = pd.DataFrame({
            "Candidate": df[candidate_col],
            "Target Role": df[role_col] if role_col else "Unknown",
            "Match Level (vs pasted JD)": computed_match_levels
        }).sort_values("Match Level (vs pasted JD)", ascending=False).head(50).reset_index(drop=True)
        recommendations["Match Level (vs pasted JD)"] = recommendations["Match Level (vs pasted JD)"].apply(make_badge)
        datatype = ["str", "str", "markdown"]
    else:
        recommendations = pd.DataFrame({
            "Message": ["Candidate recommendation fields were not found in the uploaded file."]
        })
        datatype = ["str"]

    # ========================================================
    # STATUS MESSAGE
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
        "✅ **Analysis completed successfully.**",
        "",
        f"**Records processed:** {total_records:,}",
        f"**Columns detected:** {', '.join(detected) if detected else 'Basic dataset only'}",
    ]

    if missing_notes:
        status_lines.append("")
        status_lines.append("_Notes on this file (not errors — just what could not be found):_")
        for note in missing_notes:
            status_lines.append(f"- {note}")

    status_message = "\n".join(status_lines)

    overview_kpi_html = kpi_grid([
        kpi_card("Recruitment Records", f"{total_records:,}", "#4f46e5"),
        kpi_card("Unique Candidates", f"{unique_candidates:,}", "#4f46e5"),
        kpi_card("Unique Roles", f"{unique_roles:,}", "#4f46e5"),
        kpi_card("Reusable Candidates", f"{reusable_candidates:,}", "#10b981"),
    ])

    matching_kpi_html = kpi_grid([
        kpi_card("Candidate-Role Matches", f"{match_count:,}", "#4f46e5"),
        kpi_card("HIGH Matches", f"{high_matches:,}", "#10b981"),
        kpi_card("High-Priority Matches", f"{high_priority_matches:,}", "#f59e0b"),
        kpi_card("High Joining-Risk Rows", f"{high_risk_matches:,}", "#dc2626"),
    ])

    overview_insight = insight_box(
        f"📌 <b>{reusable_candidates:,}</b> of {unique_candidates:,} unique candidates "
        f"({(reusable_candidates/unique_candidates*100) if unique_candidates else 0:.0f}%) already match more "
        f"than one role — a ready-made talent pool that needs no fresh sourcing."
    ) if unique_candidates else ""

    return (
        status_message,
        overview_kpi_html,
        matching_kpi_html,
        business_summary, business_bar, business_donut, business_insight,
        role_summary, role_insight,
        match_summary, match_donut, match_insight,
        risk_summary, risk_donut, risk_insight,
        priority_summary, priority_donut, priority_insight,
        gr.update(value=recommendations, datatype=datatype),
    )


# ============================================================
# 7. GRADIO UI
# ============================================================

CUSTOM_CSS = """
.gradio-container {
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif !important;
    max-width: 1200px !important;
    margin: auto !important;
}
#header-block {
    background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 18px;
    color: white !important;
}
#header-block h1, #header-block p { color: white !important; }
.section-title {
    font-size: 20px !important;
    font-weight: 800 !important;
    margin-top: 22px !important;
    margin-bottom: 4px !important;
    color: #111827 !important;
}
"""

with gr.Blocks(title="Recruitment Intelligence Dashboard", theme=gr.themes.Soft(primary_hue="indigo"), css=CUSTOM_CSS) as demo:

    gr.HTML("""
    <div id="header-block">
      <h1 style="margin:0;font-size:26px;">📊 Recruitment Intelligence Dashboard</h1>
      <p style="margin:8px 0 0 0;font-size:15px;opacity:0.95;">
        Analyze recruitment data, candidate-role matching, recruiter priorities and joining-risk
        from an uploaded CSV or XLSX file — works on processed pipeline files and brand-new
        recruiter trackers alike.
      </p>
    </div>
    """)

    with gr.Row():
        file_input = gr.File(label="📁 Upload Recruitment Data", file_types=[".csv", ".xlsx", ".xls"], type="filepath")
        jd_input = gr.Textbox(
            label="📝 Job Description (optional — enables Match scoring on unseen files)",
            lines=3,
            placeholder="Paste the role/JD here to score candidates against it..."
        )

    analyze_button = gr.Button("🔍 Analyze Recruitment Data", variant="primary", size="lg")

    status_box = gr.Markdown("Upload a recruitment CSV/XLSX file and click **Analyze Recruitment Data**.")

    with gr.Tabs():

        with gr.Tab("📈 Overview"):
            gr.Markdown("### Recruitment Overview", elem_classes="section-title")
            overview_kpis = gr.HTML()
            overview_insight_html = gr.HTML()

            gr.Markdown("### Recruitment by Business Group", elem_classes="section-title")
            with gr.Row():
                with gr.Column(scale=1):
                    business_donut_plot = gr.Plot(label="Share by Business Group")
                with gr.Column(scale=1):
                    business_bar_plot = gr.Plot(label="Ranked by Volume")
            business_insight_html = gr.HTML()
            business_table = gr.Dataframe(headers=["Business Group", "Candidate Records"], interactive=False)

            gr.Markdown("### Top Recruitment Roles", elem_classes="section-title")
            role_insight_html = gr.HTML()
            role_table = gr.Dataframe(headers=["Role", "Candidate Records"], interactive=False)

        with gr.Tab("🎯 Matching & Quality"):
            gr.Markdown("### Candidate-Role Matching", elem_classes="section-title")
            matching_kpis = gr.HTML()

            gr.Markdown("### Match Quality", elem_classes="section-title")
            match_plot_component = gr.Plot()
            match_insight_html = gr.HTML()
            match_table = gr.Dataframe(headers=["Match Level", "Matches"], interactive=False)

        with gr.Tab("⚠️ Risk & Priority"):
            gr.Markdown("### Joining-Risk Overview", elem_classes="section-title")
            risk_plot_component = gr.Plot()
            risk_insight_html = gr.HTML()
            risk_table = gr.Dataframe(headers=["Joining Risk Level", "Candidate-Role Rows"], interactive=False)

            gr.Markdown("### Recruiter Prioritization", elem_classes="section-title")
            priority_plot_component = gr.Plot()
            priority_insight_html = gr.HTML()
            priority_table = gr.Dataframe(headers=["Priority Category", "Matches"], interactive=False)

        with gr.Tab("🏆 Recommendations"):
            gr.Markdown("### Top Candidate Recommendations", elem_classes="section-title")
            gr.Markdown("_Sorted by match score and joining-risk score, where available._")
            recommendation_table = gr.Dataframe(interactive=False, wrap=True)

    analyze_button.click(
        fn=analyze_recruitment,
        inputs=[file_input, jd_input],
        outputs=[
            status_box,
            overview_kpis,
            matching_kpis,
            business_table, business_bar_plot, business_donut_plot, business_insight_html,
            role_table, role_insight_html,
            match_table, match_plot_component, match_insight_html,
            risk_table, risk_plot_component, risk_insight_html,
            priority_table, priority_plot_component, priority_insight_html,
            recommendation_table,
        ]
    )

print("\nLaunching Recruitment Intelligence Dashboard...")
demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)), theme=gr.themes.Soft())
