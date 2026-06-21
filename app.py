from flask import Flask, render_template, request, redirect, session, url_for
import PyPDF2
import docx
import json
import re
from groq import Groq

from PIL import Image
import pytesseract

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from flask import send_file
import io 

import os
from dotenv import load_dotenv

load_dotenv() 
print("SECRET_KEY =", os.getenv("SECRET_KEY"))
print("GROQ_API_KEY =", os.getenv("GROQ_API_KEY"))  

# Tesseract-OCR 
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe" 

from db import SessionLocal
import models

app = Flask(__name__) 
app.secret_key = "mycareercopilot123"  

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)     

def is_valid_resume(text):
    text = text.lower()

    keywords = [
        "education",
        "skills",
        "experience",
        "project",
        "projects",
        "internship",
        "certification",
        "certifications",
        "objective",
        "summary"
    ]

    matches = sum(1 for keyword in keywords if keyword in text)

    if len(text.strip()) < 100:
        return False

    return matches >= 2 

def extract_text_from_image(file):
    image = Image.open(file)
    text = pytesseract.image_to_string(image)
    return text

def calculate_match(resume_text, jd_text):
    # convert to lowercase
    resume_text = resume_text.lower()
    jd_text = jd_text.lower()
    # important keywords
    keywords = [
        "python", "flask", "sql", "aws", "docker",
        "machine learning", "react", "javascript",
        "html", "css", "git", "rest api",
        "tensorflow", "opencv", "nlp"
    ]
    matched = []
    missing = []
    for skill in keywords:
        if skill in jd_text:

            if skill in resume_text:
                matched.append(skill)
            else:
                missing.append(skill)

    total = len(matched) + len(missing)

    if total == 0:
        return 0, []

    score = int((len(matched) / total) * 100)

    return score, missing

# ================= HOME =================
@app.route("/")
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():

    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        db = SessionLocal()

        user = db.query(models.User).filter_by(email=email).first()

        if user and user.password == password:
            session["user"] = user.email
            db.close()
            return redirect(url_for("dashboard"))

        db.close()
        return render_template(
            "login.html",
            error="Invalid email or password"
        )

    return render_template("login.html")

# ================= SIGNUP =================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        return redirect(url_for("login"))
    return render_template("signup.html")


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

#------------------FORGOT_PASSWORD-------------
@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html") 

#----------------CHATBOT-----------------
@app.route("/chatbot", methods=["GET", "POST"])
def chatbot():

    if "user" not in session:
        return redirect(url_for("login"))

    reply = ""

    if request.method == "POST":

        user_message = request.form.get("message")

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": f"""
You are an AI Career Assistant.

Answer career, resume, interview,
skills and job related questions.

Question:
{user_message}
"""
                }
            ],
            temperature=0.5
        )

        reply = response.choices[0].message.content

    return render_template(
        "chatbot.html",
        reply=reply
    ) 

# ================= HISTORY =================
@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("login"))  

    db = SessionLocal()
    reports = []

    try:
        user = db.query(models.User).filter_by(email=session.get("user")).first()

        if user:
            data = db.query(models.Reports).filter_by(user_id=user.id).all()

            for r in data:
                try:
                    parsed = json.loads(r.result)
                except:
                    parsed = {}

                reports.append({
    "id": r.id,
    "resume": r.resume_text,
    "ats_score": parsed.get("ats_score", 0),
    "skills": parsed.get("skills", []),
    "missing_skills": parsed.get("missing_skills", []),
    "roadmap": parsed.get("roadmap", []),
    "interview_questions": parsed.get("interview_questions", []),   # 👈 comma added
    "resume_tips": parsed.get("resume_tips", [])
}) 

    finally:
        db.close()

    return render_template("history.html", reports=reports)

#--------DELETE SINGLE HISTORY--------------
@app.route("/delete_history/<int:id>")
def delete_history(id):
    db = SessionLocal() 

    try:
        report = db.query(models.Reports).filter_by(id=id).first()

        if report:
            db.delete(report)
            db.commit()

    finally:
        db.close()

    return redirect(url_for("history")) 

#---------------DELETE ALL HISTORY-----------------
@app.route("/delete_all_history")
def delete_all_history():
    db = SessionLocal()

    try:
        db.query(models.Reports).delete()
        db.commit()

    finally:
        db.close()

    return redirect(url_for("history"))

#-----------------DOWNLOAD_REPORT----------------  
@app.route("/download_report")
def download_report():
    result = session.get("last_result")
    if not result:
        return "No report found"
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    content = []
    content.append(
        Paragraph("AI Career Copilot Report", styles["Title"])
    )
    content.append(Spacer(1, 12))
    content.append(
        Paragraph(
            f"ATS Score: {result.get('ats_score', 0)}%",
            styles["Normal"]
        )
    )
    content.append(Spacer(1, 12))
    content.append(
        Paragraph("Skills", styles["Heading2"])
    )
    for skill in result.get("skills", []):
        content.append(
            Paragraph(f"• {skill}", styles["Normal"])
        )
    content.append(Spacer(1, 12))
    content.append(
        Paragraph("Resume Tips", styles["Heading2"])
    )
    for tip in result.get("resume_tips", []):
        content.append(
            Paragraph(f"• {tip}", styles["Normal"])
        )
    doc.build(content)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="Resume_Report.pdf",
        mimetype="application/pdf"
    )   

# ================= DASHBOARD =================
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    result = None

    if request.method == "POST":
        file = request.files.get("file")
        resume_text = ""

        try:
            # PDF
            if file and file.filename.endswith(".pdf"):
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    resume_text += page.extract_text() or ""

            # DOCX
            elif file and file.filename.endswith(".docx"):
                doc = docx.Document(file)
                resume_text = "\n".join([p.text for p in doc.paragraphs])

            # IMAGE (JPG/JPEG/PNG)
            elif file and file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                resume_text = extract_text_from_image(file)

            # TEXT AREA
            else:
                resume_text = request.form.get("resume", "")

            print("RESUME TEXT =")
            print(resume_text)
            print("TEXT LENGTH =", len(resume_text))

            role = request.form.get("role") or "Software Engineer" 
            job_description = request.form.get("job_description", "") 
            print("JOB DESCRIPTION =")
            print(job_description)

            if not is_valid_resume(resume_text):
                result = {"error": "Please upload a valid resume."}
            else:
                prompt = f"""
You are an ATS Resume Analyzer.

Return ONLY valid JSON in this exact format:

{{
  "ats_score": 0,
  "skills": [],
  "missing_skills": [],
  "roadmap": [],
  "interview_questions": [],
  "resume_tips": []  
}}

Rules:
- Return ONLY these keys.
- ats_score must be a number from 0 to 100.
- skills must be list of strings.
- missing_skills must be list of strings.
- roadmap must be list of strings.
- interview_questions must be list of strings.
- resume_tips must be list of strings.
- Do not return name, description, education, projects, certifications or experience.
- No explanation outside JSON.
- skills must NEVER be empty. Extract all technical skills found in the resume.
- resume_tips must contain 5 to 8 personalized resume improvement suggestions.
- Tips should be short and actionable.
- Focus on ATS optimization, skills, projects, certifications and resume quality.

Role: {role}

Resume:
{resume_text}
"""

                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0
                )

                content = response.choices[0].message.content.strip()

                if "```" in content:
                    content = content.replace("```json", "").replace("```", "").strip()

                try:
                    result = json.loads(content)
                    print("RAW AI RESPONSE =", content)
                    print(result)
                    print("RESULT =", result)
                    print("ATS =", result.get("ats_score"))
                    print("RESUME TIPS =", result.get("resume_tips"))

                except:
                    start = content.find("{")
                    end = content.rfind("}") + 1
                    result = json.loads(content[start:end])
                    print("RAW AI RESPONSE =", content)
                    print("PARSED RESULT =", result)

                # ✅ SAFE ATS FIX
                result["ats_score"] = int(result.get("ats_score", 0))
                result.setdefault("ats_score", 0)
                result.setdefault("skills", [])
                result.setdefault("missing_skills", [])
                result.setdefault("roadmap", [])
                result.setdefault("interview_questions", []) 
                result.setdefault("resume_tips", [])

                # JOB DESCRIPTION MATCH
                match_score, missing_keywords = calculate_match(
                    resume_text,
                    job_description
                )

                result["match_score"] = match_score
                result["missing_keywords"] = missing_keywords
                
                session["last_result"] = result 
                
                print("MATCH SCORE =", match_score)
                print("MISSING KEYWORDS =", missing_keywords)


                # normalize lists
                for key in ["skills", "missing_skills", "roadmap", "interview_questions","resume_tips"]:
                    if isinstance(result.get(key), str):
                        result[key] = [result[key]]
                    if not result.get(key):
                        result[key] = []

                # SAVE DB
                db = SessionLocal()
                try:
                    user = db.query(models.User).filter_by(email=session.get("user")).first()

                    if user:
                        report = models.Reports(
                            user_id=user.id,
                            resume_text=resume_text,
                            result=json.dumps(result)
                        )
                        db.add(report)
                        db.commit()

                finally:
                    db.close()

        except Exception as e:
            result = {"error": str(e)}

    return render_template("dashboard.html", result=result)

# ================= MOCK TEST QUESTIONS =================
questions = [
    {
        "question": "What is JVM?",
        "options": [
            "Java Virtual Machine",
            "Java Vendor Machine",
            "Joint Virtual Machine",
            "None"
        ],
        "answer": "Java Virtual Machine"
    },
    {
        "question": "Which keyword is used for inheritance?",
        "options": ["implements", "extends", "inherit", "super"],
        "answer": "extends"
    },
    {
        "question": "Which language is used for Flask?",
        "options": ["Java", "Python", "C++", "PHP"],
        "answer": "Python"
    },
    {
        "question": "Which method is the entry point of a Java program?",
        "options": ["start()", "main()", "run()", "execute()"],
        "answer": "main()"
    },
    {
        "question": "Which symbol is used for comments in Python?",
        "options": ["//", "#", "/* */", "--"],
        "answer": "#"
    },
    {
        "question": "What does SQL stand for?",
        "options": [
            "Structured Query Language",
            "Simple Query Language",
            "System Query Logic",
            "None"
        ],
        "answer": "Structured Query Language"
    },
    {
        "question": "Which database are you using in this project?",
        "options": ["MongoDB", "TiDB", "SQLite", "PostgreSQL"],
        "answer": "TiDB"
    },
    {
        "question": "Which HTML tag is used for hyperlinks?",
        "options": ["<link>", "<a>", "<href>", "<url>"],
        "answer": "<a>"
    },
    {
        "question": "Which CSS property changes text color?",
        "options": ["font-color", "text-color", "color", "style"],
        "answer": "color"
    },
    {
        "question": "What is the default port of Flask?",
        "options": ["3000", "5000", "8000", "8080"],
        "answer": "5000"
    },
    {
        "question": "Which keyword creates a function in Python?",
        "options": ["func", "function", "define", "def"],
        "answer": "def"
    },
    {
        "question": "Which HTTP method is used to submit forms?",
        "options": ["GET", "POST", "PUT", "DELETE"],
        "answer": "POST"
    },
    {
        "question": "Which operator is used for equality in Python?",
        "options": ["=", "==", "!=", "==="],
        "answer": "=="
    },
    {
        "question": "Which company developed Java?",
        "options": ["Google", "Microsoft", "Sun Microsystems", "IBM"],
        "answer": "Sun Microsystems"
    },
    {
        "question": "Which data structure uses FIFO?",
        "options": ["Stack", "Queue", "Tree", "Graph"],
        "answer": "Queue"
    },
    {
        "question": "Which data structure uses LIFO?",
        "options": ["Stack", "Queue", "Tree", "Graph"],
        "answer": "Stack"
    },
    {
        "question": "Which keyword is used to define a class in Python?",
        "options": ["object", "class", "Class", "define"],
        "answer": "class"
    },
    {
        "question": "Which HTML tag is used for images?",
        "options": ["<image>", "<img>", "<picture>", "<src>"],
        "answer": "<img>"
    },
    {
        "question": "What does API stand for?",
        "options": [
            "Application Programming Interface",
            "Advanced Program Integration",
            "Application Process Integration",
            "None"
        ],
        "answer": "Application Programming Interface"
    },
    {
        "question": "Which CSS property is used for rounded corners?",
        "options": [
            "corner-radius",
            "border-radius",
            "radius",
            "round-corner"
        ],
        "answer": "border-radius"
    }
] 

# ================= MOCK TEST PAGE =================
@app.route("/mock_test")
def mock_test():
    return render_template("mock_test.html", questions=questions)

# ================= SUBMIT TEST =================
@app.route("/submit_test", methods=["POST"])
def submit_test():

    score = 0
    total = len(questions)

    print("TOTAL =", total)
    print("FORM =", request.form)

    for i, q in enumerate(questions):

        user_answer = request.form.get(f"q{i}")

        if user_answer == q["answer"]:
            score += 1

    print("FINAL SCORE =", score)

    return render_template(
        "result.html",
        score=score,
        total=total
    ) 


# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)  





