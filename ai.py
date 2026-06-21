import json
from groq import Groq

client = api_key=os.getenv("GROQ_API_KEY")  

def analyze_resume(resume_text, user_goal):

    prompt = f"""
You are a senior software engineer and hiring manager.

Analyze this resume for role: {user_goal}

Return ONLY valid JSON with keys:
ats_score, skills, missing_skills, roadmap, interview_questions

IMPORTANT RULES:
- ats_score MUST be a number between 0 and 100
- skills MUST be an ARRAY of strings
- missing_skills MUST be an ARRAY of strings
- roadmap MUST be an ARRAY of strings
- interview_questions MUST be an ARRAY
- No markdown
- Only JSON

Resume:
{resume_text}
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "Return ONLY valid JSON with keys: ats_score, skills, missing_skills, roadmap, interview_questions"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    # Remove markdown if model returns it
    if "```" in content:
        content = content.replace("```json", "").replace("```", "").strip()

    # Safe JSON parsing
    try:
        data = json.loads(content)
    except:
        start = content.find("{")
        end = content.rfind("}") + 1
        data = json.loads(content[start:end])

    # ATS Score
    ats_score = data.get("ats_score", 0)

    # Roadmap handling
    raw_roadmap = data.get("roadmap", [])

    flat_roadmap = []

    if isinstance(raw_roadmap, str):
        flat_roadmap = [raw_roadmap]

    elif isinstance(raw_roadmap, dict):
        flat_roadmap = [raw_roadmap.get("description", str(raw_roadmap))]

    elif isinstance(raw_roadmap, list):
        for item in raw_roadmap:
            if isinstance(item, dict):
                flat_roadmap.append(
                    item.get("description") or
                    item.get("step") or
                    str(item)
                )
            else:
                flat_roadmap.append(str(item))

    # Interview questions handling
    flat_questions = []

    for item in data.get("interview_questions", []):
        if isinstance(item, dict):
            q = item.get("question", "")
            a = item.get("answer", "")
            flat_questions.append(f"{q} → {a}")
        else:
            flat_questions.append(str(item))

    result = {
        "ats_score": ats_score,
        "skills": data.get("skills", []),
        "missing_skills": data.get("missing_skills", []),
        "roadmap": flat_roadmap,
        "interview_questions": flat_questions
    }

    print("ATS SCORE =", ats_score)  # Debug

    return result


if __name__ == "__main__":
    sample_resume = "Python, Flask, HTML, CSS, SQL"

    result = analyze_resume(
        sample_resume,
        "Backend Developer"
    )

    print(json.dumps(result, indent=2)) 