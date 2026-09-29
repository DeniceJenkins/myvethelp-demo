"""
MyVetHelp Demo App
-------------------
A simple prototype that lets a veteran type a question in plain language
and find the closest-matching resource from the MyVetHelp_Resource_Database.xlsx
spreadsheet.

HOW TO RUN THIS (for your group):
1. Install requirements (one time):
     pip install streamlit openpyxl pandas openai
2. Put "MyVetHelp_Resource_Database.xlsx" in the same folder as this file,
   along with the .streamlit folder (keeps the color theme).
3. Run:
     streamlit run app.py
4. It opens automatically in your browser.

This version uses simple keyword matching to find the best resource(s)
for a typed question. AI phrasing is OPTIONAL: if your group enters
Azure OpenAI credentials in the sidebar, the app will use AI to turn the
matched resource(s) into a friendly written answer. Without credentials,
it just displays the matched resource(s) directly -- so the app always
works, with or without a key.

TO ENABLE AI PHRASING:
You need three things from your school's Azure OpenAI resource:
  1. Endpoint       (looks like: https://your-resource-name.openai.azure.com/)
  2. API key
  3. Deployment name (the name YOU gave the model when you deployed it
                       in Azure AI Foundry / Azure OpenAI Studio, e.g. "gpt-4o")
Enter these in the sidebar once the app is running. Ask whoever set up
your school's Azure account for these three values if you don't have them.
"""

import html
import re

import pandas as pd
import streamlit as st

st.set_page_config(page_title="MyVetHelp (Demo)", page_icon="🎖️", layout="centered")

# ---------- Visual identity ----------
# Palette: navy (ink/trust), parchment (warm neutral bg), brass (primary accent),
# deep red (urgent/crisis), slate teal (secondary accent) -- chosen to read as
# an official service resource rather than a generic app.
NAVY = "#16233B"
PANEL = "#F3ECDC"
BRASS = "#9C7A2E"
DEEP_RED = "#8C2F2F"
SLATE_TEAL = "#3F6B6B"
BORDER = "#DDD3BC"
TEXT_MUTED = "#4A4F58"

CATEGORY_COLOR = {
    "Disability Benefits": BRASS,
    "Health Care": SLATE_TEAL,
    "Mental Health": DEEP_RED,
    "Housing": NAVY,
    "Employment": SLATE_TEAL,
    "Education": BRASS,
}
DEFAULT_ACCENT = NAVY

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@500;600;700&family=Public+Sans:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Public Sans', sans-serif;
        color: {NAVY};
    }}

    .mvh-hero {{
        background: {NAVY};
        border-radius: 10px;
        padding: 1.9rem 2rem;
        margin-bottom: 1.6rem;
    }}
    .mvh-hero .mvh-kicker {{
        color: {BRASS};
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        margin-bottom: 0.35rem;
    }}
    .mvh-hero h1 {{
        font-family: 'Source Serif 4', serif;
        color: #FDFBF6;
        font-size: 2.1rem;
        font-weight: 700;
        margin: 0 0 0.4rem 0;
        line-height: 1.15;
    }}
    .mvh-hero p {{
        color: #C9D1DE;
        font-size: 1.02rem;
        margin: 0;
        max-width: 46ch;
    }}

    .mvh-section-label {{
        font-family: 'Source Serif 4', serif;
        font-size: 1.25rem;
        font-weight: 600;
        color: {NAVY};
        margin: 1.1rem 0 0.7rem 0;
    }}

    .mvh-card {{
        background: #FFFFFF;
        border: 1px solid {BORDER};
        border-left: 5px solid var(--accent, {NAVY});
        border-radius: 6px;
        padding: 1.05rem 1.2rem;
        margin-bottom: 0.85rem;
    }}
    .mvh-card .mvh-name {{
        font-family: 'Source Serif 4', serif;
        font-size: 1.15rem;
        font-weight: 600;
        color: {NAVY};
        margin-bottom: 0.15rem;
    }}
    .mvh-card .mvh-meta {{
        color: var(--accent, {NAVY});
        font-size: 0.88rem;
        font-weight: 600;
        margin-bottom: 0.55rem;
    }}
    .mvh-card .mvh-desc {{
        color: {TEXT_MUTED};
        margin-bottom: 0.6rem;
        line-height: 1.5;
    }}
    .mvh-card .mvh-row {{
        font-size: 0.92rem;
        margin-bottom: 0.28rem;
        color: {NAVY};
    }}
    .mvh-card .mvh-row b {{
        color: {TEXT_MUTED};
        font-weight: 600;
    }}
    .mvh-card a {{
        color: {SLATE_TEAL};
        font-weight: 600;
        text-decoration: none;
    }}
    .mvh-card a:hover {{ text-decoration: underline; }}

    .mvh-answer {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 1.2rem 1.3rem;
        margin-bottom: 1rem;
        line-height: 1.55;
        color: {NAVY};
    }}

    [data-testid="stSidebar"] {{
        background: {PANEL};
    }}

    .mvh-browse-cat {{
        font-weight: 600;
        color: {NAVY};
        margin-top: 0.7rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def esc(value) -> str:
    """HTML-escape a spreadsheet value safely, treating blanks as empty text."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return html.escape(str(value))


# ---------- Sidebar: optional Azure OpenAI credentials ----------
st.sidebar.header("⚙️ AI phrasing (optional)")
st.sidebar.caption(
    "Leave these blank to show matched resources directly. "
    "Fill them in to have AI write a plain-language answer instead."
)
azure_endpoint = st.sidebar.text_input("Azure OpenAI endpoint", placeholder="https://your-resource.openai.azure.com/")
azure_key = st.sidebar.text_input("Azure OpenAI API key", type="password")
azure_deployment = st.sidebar.text_input("Deployment name", placeholder="e.g. gpt-4o")

ai_enabled = bool(azure_endpoint and azure_key and azure_deployment)


def get_ai_response(user_question, matched_rows):
    """
    Sends the matched resource info + the user's question to Azure OpenAI
    and asks it to write a short, friendly answer using ONLY that info.
    Returns None (and lets the app fall back to plain display) on any error.
    """
    try:
        from openai import AzureOpenAI
    except ImportError:
        st.sidebar.error("Missing package. Run: pip install openai")
        return None

    resource_text = "\n\n".join(
        f"Resource: {r['Resource Name']}\n"
        f"Category: {r['Category']}\n"
        f"Description: {r['Description']}\n"
        f"Eligibility: {r['Eligibility (brief)']}\n"
        f"How to Apply: {r['How to Apply']}\n"
        f"Link: {r['Link']}\n"
        f"Contact: {r['Contact/Phone']}"
        for _, r in matched_rows.iterrows()
    )

    system_prompt = (
        "You are MyVetHelp, an assistant that helps veterans find the right support "
        "resource. You must ONLY use the resource information provided below. "
        "Do not invent any facts, links, phone numbers, or eligibility rules that "
        "are not explicitly given. Write a short, warm, plain-language answer (3-5 "
        "sentences) that tells the veteran which resource(s) fit their question and "
        "how to take the next step. Always include the relevant link and contact "
        "info exactly as given."
    )

    try:
        client = AzureOpenAI(
            azure_endpoint=azure_endpoint,
            api_key=azure_key,
            api_version="2024-08-01-preview",
        )
        completion = client.chat.completions.create(
            model=azure_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Veteran's question: {user_question}\n\nMatched resources:\n{resource_text}"},
            ],
            temperature=0.3,
            max_tokens=350,
        )
        return completion.choices[0].message.content
    except Exception as e:
        st.sidebar.error(f"AI request failed, showing resources directly instead.\n\n({e})")
        return None


# ---------- Load data ----------
@st.cache_data
def load_resources():
    df = pd.read_excel("MyVetHelp_Resource_Database.xlsx", sheet_name="Resources", header=2)
    # Drop the example row so it doesn't show up as a real result
    df = df[~df["Resource Name"].astype(str).str.startswith("EXAMPLE")]
    df = df.dropna(subset=["Resource Name"])
    return df.reset_index(drop=True)


resources = load_resources()


# ---------- Simple keyword search ----------
def score_row(query_words, row):
    """Count how many query words appear in the resource's searchable text."""
    searchable = " ".join([
        str(row.get("Resource Name", "")),
        str(row.get("Category", "")),
        str(row.get("Description", "")),
        str(row.get("Eligibility (brief)", "")),
    ]).lower()
    return sum(1 for w in query_words if w in searchable)


def find_matches(query, df, top_n=3):
    query_words = re.findall(r"[a-z]+", query.lower())
    stopwords = {"the", "a", "an", "i", "my", "to", "for", "and", "of", "in",
                 "on", "with", "how", "do", "get", "need", "want", "help", "am"}
    query_words = [w for w in query_words if w not in stopwords and len(w) > 2]

    if not query_words:
        return pd.DataFrame()

    scored = df.copy()
    scored["match_score"] = scored.apply(lambda r: score_row(query_words, r), axis=1)
    scored = scored[scored["match_score"] > 0]
    scored = scored.sort_values("match_score", ascending=False)
    return scored.head(top_n)


def render_resource_card(row):
    accent = CATEGORY_COLOR.get(str(row.get("Category", "")).strip(), DEFAULT_ACCENT)
    link = esc(row.get("Link", ""))
    st.markdown(
        f"""
        <div class="mvh-card" style="--accent: {accent};">
            <div class="mvh-name">{esc(row.get('Resource Name', ''))}</div>
            <div class="mvh-meta">{esc(row.get('Category', ''))} &nbsp;·&nbsp; {esc(row.get('Region', ''))}</div>
            <div class="mvh-desc">{esc(row.get('Description', ''))}</div>
            <div class="mvh-row"><b>Eligibility</b> &nbsp;{esc(row.get('Eligibility (brief)', ''))}</div>
            <div class="mvh-row"><b>How to apply</b> &nbsp;{esc(row.get('How to Apply', ''))}</div>
            <div class="mvh-row"><b>Form</b> &nbsp;{esc(row.get('Form #', ''))}</div>
            <div class="mvh-row"><b>Contact</b> &nbsp;{esc(row.get('Contact/Phone', ''))}</div>
            <div class="mvh-row"><a href="{link}" target="_blank">{link}</a></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- UI ----------
st.markdown(
    """
    <div class="mvh-hero">
        <div class="mvh-kicker">🎖️ Veteran resource navigator — demo</div>
        <h1>MyVetHelp</h1>
        <p>Tell it what you're dealing with, in your own words. It points you to a real,
        vetted resource instead of guessing.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("About this demo"):
    st.write(
        "This prototype searches a curated list of real veteran resources "
        "(disability benefits, health care, mental health, housing, employment, "
        "and education) and shows the closest matches. It does not generate its "
        "own advice -- every answer points to a real, human-curated resource."
    )

query = st.text_input(
    "What do you need help with?",
    placeholder="e.g. I don't know how to file for disability benefits",
)

if query:
    matches = find_matches(query, resources)

    if matches.empty:
        st.warning(
            "No close matches found in the current resource list. "
            "Try different words, or browse all resources below."
        )
    else:
        ai_answer = None
        if ai_enabled:
            with st.spinner("Thinking..."):
                ai_answer = get_ai_response(query, matches)

        if ai_answer:
            st.markdown('<div class="mvh-section-label">Answer</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="mvh-answer">{esc(ai_answer)}</div>', unsafe_allow_html=True)
            with st.expander("See the matched resource details"):
                for _, row in matches.iterrows():
                    render_resource_card(row)
        else:
            label = "Found 1 matching resource" if len(matches) == 1 else f"Found {len(matches)} matching resources"
            st.markdown(f'<div class="mvh-section-label">{label}</div>', unsafe_allow_html=True)
            for _, row in matches.iterrows():
                render_resource_card(row)

st.divider()

with st.expander("Browse all resources in the database"):
    for cat in sorted(resources["Category"].dropna().unique()):
        accent = CATEGORY_COLOR.get(cat, DEFAULT_ACCENT)
        st.markdown(
            f'<div class="mvh-browse-cat" style="color:{accent};">{esc(cat)}</div>',
            unsafe_allow_html=True,
        )
        cat_rows = resources[resources["Category"] == cat]
        for _, row in cat_rows.iterrows():
            st.markdown(f"- {esc(row['Resource Name'])} ({esc(row['Region'])})")
