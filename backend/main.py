from fastapi import FastAPI, Depends, HTTPException, Header
from dotenv import load_dotenv
import os
import json
from supabase import create_client, Client
from groq import Groq
from priority_engine import calculate_priority, get_priority_category

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="StudyPlanner AI API")


@app.get("/")
def health_check():
    return {"status": "ok", "message": "StudyPlanner AI backend is running"}


def get_supabase_client(authorization: str = Header(None)) -> Client:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    client.postgrest.auth(token)
    return client


def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header"
        )

    parts = authorization.split(" ", 1)

    if len(parts) != 2 or not parts[1].strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header"
        )

    token = parts[1].strip()

    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        user_response = client.auth.get_user(token)

        if not user_response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )

        return user_response.user.id

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )


@app.get("/subjects")
def get_subjects(
    supabase: Client = Depends(get_supabase_client),
    user_id: str = Depends(get_current_user_id)
):
    response = supabase.table("subjects").select("*").execute()
    return response.data

@app.get("/topic-priorities")
def get_topic_priorities(
    supabase: Client = Depends(get_supabase_client),
    user_id: str = Depends(get_current_user_id)
):
    # Get the authenticated user's subjects
    subjects_response = (
        supabase
        .table("subjects")
        .select("*")
        .execute()
    )

    subjects = subjects_response.data

    if not subjects:
        return {
            "message": "No subjects found",
            "priorities": []
        }

    priorities = []

    for subject in subjects:

        # Get topics belonging to this subject
        topics_response = (
            supabase
            .table("topics")
            .select("*")
            .eq("subject_id", subject["id"])
            .execute()
        )

        topics = topics_response.data

        # Get upcoming exams for this subject
        exams_response = (
            supabase
            .table("exams")
            .select("*")
            .eq("subject_id", subject["id"])
            .order("exam_date")
            .execute()
        )

        exams = exams_response.data

        # Use the nearest exam date
        exam_date = None

        if exams:
            exam_date = exams[0]["exam_date"]

        # Calculate priority for every topic
        for topic in topics:

            # Prefer topic difficulty.
            # Fall back to subject difficulty if needed.
            difficulty = topic.get("difficulty")

            if difficulty is None:
                difficulty = subject.get("difficulty", 3)

            mastery_level = topic.get("mastery_level", 0)

            score = calculate_priority(
                exam_date=exam_date,
                difficulty=difficulty,
                mastery_level=mastery_level
            )

            category = get_priority_category(score)

            priorities.append({
                "subject_id": subject["id"],
                "subject": subject["name"],
                "topic_id": topic["id"],
                "topic": topic["name"],
                "exam_date": exam_date,
                "difficulty": difficulty,
                "mastery_level": mastery_level,
                "priority_score": score,
                "priority_category": category
            })

    # Highest priority first
    priorities.sort(
        key=lambda item: item["priority_score"],
        reverse=True
    )

    return {
        "user_id": user_id,
        "priorities": priorities
    }



@app.post("/generate-plan")
def generate_plan(
    supabase: Client = Depends(get_supabase_client),
    user_id: str = Depends(get_current_user_id),
):
    # -----------------------------------
    # 1. Get user's profile
    # -----------------------------------
    profile_response = (
        supabase
        .table("profiles")
        .select("daily_study_hours")
        .eq("id", user_id)
        .execute()
    )

    if not profile_response.data:
        raise HTTPException(
            status_code=404,
            detail="User profile not found"
        )

    daily_hours = float(
        profile_response.data[0].get("daily_study_hours") or 2
    )

    # -----------------------------------
    # 2. Get user's subjects
    # -----------------------------------
    subjects_response = (
        supabase
        .table("subjects")
        .select("*")
        .execute()
    )

    subjects = subjects_response.data

    if not subjects:
        raise HTTPException(
            status_code=400,
            detail="No subjects found for this user"
        )

    priorities = []

    # -----------------------------------
    # 3. Get topics and exams
    # -----------------------------------
    for subject in subjects:

        topics_response = (
            supabase
            .table("topics")
            .select("*")
            .eq("subject_id", subject["id"])
            .execute()
        )

        exams_response = (
            supabase
            .table("exams")
            .select("*")
            .eq("subject_id", subject["id"])
            .order("exam_date")
            .execute()
        )

        topics = topics_response.data
        exams = exams_response.data

        exam_date = None

        if exams:
            exam_date = exams[0]["exam_date"]

        # -----------------------------------
        # 4. Calculate priority per topic
        # -----------------------------------
        for topic in topics:

            difficulty = topic.get(
                "difficulty",
                subject.get("difficulty", 3)
            )

            mastery_level = topic.get("mastery_level", 0)

            priority_score = calculate_priority(
                exam_date=exam_date,
                difficulty=difficulty,
                mastery_level=mastery_level
            )

            priorities.append({
                "subject_id": subject["id"],
                "subject": subject["name"],
                "topic_id": topic["id"],
                "topic": topic["name"],
                "exam_date": exam_date,
                "difficulty": difficulty,
                "mastery_level": mastery_level,
                "priority_score": priority_score,
                "priority_category": get_priority_category(
                    priority_score
                )
            })

    if not priorities:
        raise HTTPException(
            status_code=400,
            detail="No topics found. Add topics before generating a plan."
        )

    # Highest priority first
    priorities.sort(
        key=lambda item: item["priority_score"],
        reverse=True
    )

    # -----------------------------------
    # 5. Send priorities to Groq
    # -----------------------------------
    prompt = f"""
You are an intelligent study planning system.

Create a personalized daily study timetable.

The student has {daily_hours} hours available for studying each day.

Here are the topics ranked by priority:

{json.dumps(priorities, indent=2)}

Rules:

1. Prioritize higher priority_score topics.
2. Focus more time on weak topics with low mastery_level.
3. Schedule topics before their exam_date.
4. Do not exceed {daily_hours} total study hours per day.
5. Create realistic study sessions.
6. Use the topic_id and subject_id provided.
7. Return ONLY valid JSON.

Return exactly this structure:

{{
  "tasks": [
    {{
      "subject_id": "uuid",
      "topic_id": "uuid",
      "title": "string",
      "description": "string",
      "task_date": "YYYY-MM-DD",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "priority": 1
    }}
  ]
}}

Priority mapping:

5 = Critical
4 = High
3 = Medium
2 = Low
1 = Very Low
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        response_format={
            "type": "json_object"
        },
    )

    # -----------------------------------
    # 6. Parse AI response
    # -----------------------------------
    plan = json.loads(
        response.choices[0].message.content
    )

    if "tasks" not in plan:
        raise HTTPException(
            status_code=500,
            detail="AI returned an invalid plan"
        )

    # -----------------------------------
    # 7. Save tasks
    # -----------------------------------
    inserted = []

    for task in plan["tasks"]:

        result = (
            supabase
            .table("tasks")
            .insert({
                "user_id": user_id,
                "subject_id": task["subject_id"],
                "topic_id": task["topic_id"],
                "title": task["title"],
                "description": task.get("description"),
                "task_date": task["task_date"],
                "start_time": task["start_time"],
                "end_time": task["end_time"],
                "priority": task.get("priority", 3),
                "status": "pending"
            })
            .execute()
        )

        inserted.append(result.data)

    return {
        "daily_study_hours": daily_hours,
        "topics_processed": len(priorities),
        "generated_tasks": inserted
    }