import streamlit as st
import requests
import pdfplumber
import spacy
import re
import urllib.parse

# ---------------- CONFIG ----------------
st.set_page_config(page_title="Live Job Finder", layout="wide")
nlp = spacy.load("en_core_web_sm")

COMMON_SKILLS = [
    "python", "java", "javascript", "react", "django", "fastapi",
    "machine learning", "deep learning", "sql", "mongodb", "node"
]

# ---------------- FUNCTIONS ----------------

def parse_resume(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            if page.extract_text():
                text += page.extract_text() + " "

    text_lower = text.lower()
    skills = [s for s in COMMON_SKILLS if s in text_lower]

    if not skills:
        skills = ["developer", "engineer", "software"]


    experience = re.findall(r'(\d+)\s+years?', text_lower)

    doc = nlp(text)
    locations = [ent.text for ent in doc.ents if ent.label_ == "GPE"]

    return {
        "skills": list(set(skills)),
        "experience": experience[0] if experience else "Not specified",
        "location": locations[0] if locations else "Anywhere"
    }


def fetch_remotive_jobs(skills, limit=30):
    url = "https://remotive.io/api/remote-jobs"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return []
        data = response.json()
    except Exception:
        return []

    jobs = []
    for job in data.get("jobs", [])[:200]:
        text = (job.get("title", "") + " " + job.get("description", "")).lower()

        score = 0
        for skill in skills:
            if skill.lower() in text:
                score += 1

        jobs.append({
            "title": job.get("title", "N/A"),
            "company": job.get("company_name", "N/A"),
            "location": job.get("candidate_required_location", "Remote"),
            "url": job.get("url", "#"),
            "source": "Remotive",
            "match_score": score
        })

    # sort by relevance
    jobs = sorted(jobs, key=lambda x: x["match_score"], reverse=True)

    # return top results even if score = 0
    return jobs[:limit]


def generate_linkedin_url(skills, location):
    query = urllib.parse.quote(" ".join(skills))
    loc = urllib.parse.quote(location)
    return f"https://www.linkedin.com/jobs/search/?keywords={query}&location={loc}"

# ---------------- UI ----------------

st.title("🔍 Live AI Job Finder")
st.caption("No login • No database • Real-time jobs")

input_method = st.radio(
    "How do you want to provide your information?",
    ["Fill Form", "Upload Resume"]
)

skills = []
location = "Anywhere"

if input_method == "Fill Form":
    skill_input = st.text_input("Skills (comma separated)", placeholder="python, react, fastapi")
    location = st.text_input("Preferred Location", value="Anywhere")
    skills = [s.strip().lower() for s in skill_input.split(",") if s.strip()]

else:
    resume = st.file_uploader("Upload Resume (PDF only)", type=["pdf"])
    if resume:
        parsed = parse_resume(resume)
        skills = parsed["skills"]
        location = parsed["location"]

        st.subheader("📄 Extracted From Resume")
        st.write("**Skills:**", ", ".join(skills))
        st.write("**Experience:**", parsed["experience"], "years")
        st.write("**Location:**", location)

# ---------------- SEARCH ----------------

if st.button("🚀 Find Jobs"):
    if not skills:
        st.warning("Please provide skills.")
    else:
        with st.spinner("Fetching live jobs..."):
            jobs = fetch_remotive_jobs(skills)
            linkedin_url = generate_linkedin_url(skills, location)

        st.success(f"Found {len(jobs)} matching jobs")

        # ---------------- RESULTS ----------------
        for job in jobs:
            st.markdown(f"""
            ### {job['title']}
            **Company:** {job['company']}  
            **Location:** {job['location']}  
            **Source:** {job['source']}  
            **Match Score:** {job['match_score']}  

            👉 [Apply Here]({job['url']})
            ---
            """)

        # ---------------- LINKEDIN ----------------
        st.subheader("🔗 Search More on LinkedIn")
        st.markdown(f"[Open LinkedIn Job Search]({linkedin_url})")

