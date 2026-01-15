import streamlit as st
import requests
import pdfplumber
import re
import urllib.parse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Live Job Finder", layout="wide")

COMMON_SKILLS = [
    "python", "java", "javascript", "react", "django", "fastapi",
    "machine learning", "data science", "sql", "mongodb", "node"
]

if "bookmarks" not in st.session_state:
    st.session_state.bookmarks = []

# --------------------------------------------------
# UTILITIES
# --------------------------------------------------


SALARY_DATA = {
    "junior software engineer": 60000,
    "software engineer": 80000,
    "senior software engineer": 110000,
    "backend developer": 90000,
    "full stack developer": 95000,
    "machine learning engineer": 120000,
    "data scientist": 115000,
    "devops engineer": 105000,
    "frontend developer": 85000,
    "cloud architect": 130000
}

def ai_estimate_salary(job_title):
    titles = list(SALARY_DATA.keys())
    salaries = np.array(list(SALARY_DATA.values()))

    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform([job_title] + titles)

    similarities = cosine_similarity(vectors[0:1], vectors[1:]).flatten()
    best_match_idx = similarities.argmax()

    estimated_salary = salaries[best_match_idx]

    # Convert to range
    low = int(estimated_salary * 0.85)
    high = int(estimated_salary * 1.15)

    return f"${low//1000}k – ${high//1000}k"


def parse_resume(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            if page.extract_text():
                text += page.extract_text().lower()

    skills = [s for s in COMMON_SKILLS if s in text]
    exp = re.findall(r'(\d+)\s+years?', text)

    return {
        "skills": skills or ["developer"],
        "experience": exp[0] if exp else "Not specified",
        "location": "Anywhere"
    }


@st.cache_data(ttl=600)
def fetch_remotive_raw():
    try:
        res = requests.get("https://remotive.io/api/remote-jobs", timeout=10)
        if res.status_code == 200:
            return res.json().get("jobs", [])
    except Exception:
        pass
    return []


def semantic_match_jobs(skills, jobs, limit=30):
    user_text = " ".join(skills)
    job_texts = [
        job.get("title", "") + " " + job.get("description", "")
        for job in jobs
    ]

    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform([user_text] + job_texts)
    scores = cosine_similarity(vectors[0:1], vectors[1:]).flatten()

    results = []
    for job, score in zip(jobs, scores):
        results.append({
            "title": job["title"],
            "company": job["company_name"],
            "location": job["candidate_required_location"],
            "url": job["url"],
            "score": round(float(score), 2),
            "salary": ai_estimate_salary(job["title"])
        })

    return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]


def linkedin_search(skills, location):
    q = urllib.parse.quote(" ".join(skills))
    l = urllib.parse.quote(location)
    return f"https://www.linkedin.com/jobs/search/?keywords={q}&location={l}"


def indeed_search(skills, location):
    q = urllib.parse.quote(" ".join(skills))
    l = urllib.parse.quote(location)
    return f"https://www.indeed.com/jobs?q={q}&l={l}"

# --------------------------------------------------
# UI
# --------------------------------------------------

st.title("🔍 Enhanced Live Job Finder")
st.caption("Semantic matching • No login • No database")

method = st.radio("Input method", ["Manual Input", "Upload Resume"])

skills = []
location = "Anywhere"

if method == "Manual Input":
    skills = st.text_input("Skills (comma separated)").lower().split(",")
    skills = [s.strip() for s in skills if s.strip()]
else:
    resume = st.file_uploader("Upload Resume (PDF)", type=["pdf"])
    if resume:
        parsed = parse_resume(resume)
        skills = parsed["skills"]
        location = parsed["location"]
        st.info(f"Extracted skills: {', '.join(skills)}")

if not skills:
    skills = ["developer"]

# Filters
min_score = st.slider("Minimum relevance score", 0.0, 1.0, 0.1)
keyword_filter = st.text_input("Must include keyword (optional)")

# --------------------------------------------------
# SEARCH
# --------------------------------------------------

if st.button("🚀 Find Jobs"):
    with st.spinner("Matching jobs intelligently..."):
        raw_jobs = fetch_remotive_raw()
        matched = semantic_match_jobs(skills, raw_jobs)

    st.success(f"Showing {len(matched)} jobs")

    for job in matched:
        if job["score"] < min_score:
            continue
        if keyword_filter and keyword_filter.lower() not in job["title"].lower():
            continue

        col1, col2 = st.columns([4, 1])

        with col1:
            st.markdown(f"""
            ### {job['title']}
            **Company:** {job['company']}  
            **Location:** {job['location']}  
            **Relevance Score:** {job['score']}  
            **Estimated Salary:** {job['salary']}  

            👉 [Apply Here]({job['url']})
            """)

        with col2:
            if st.button("⭐ Save", key=job["url"]):
                st.session_state.bookmarks.append(job)

        st.divider()

    # External Platforms
    st.subheader("🔗 Search More")
    st.markdown(f"- [LinkedIn Jobs]({linkedin_search(skills, location)})")
    st.markdown(f"- [Indeed Jobs]({indeed_search(skills, location)})")

# --------------------------------------------------
# BOOKMARKS
# --------------------------------------------------

if st.session_state.bookmarks:
    st.subheader("⭐ Saved Jobs")
    for job in st.session_state.bookmarks:
        st.markdown(f"- **{job['title']}** at {job['company']}")
