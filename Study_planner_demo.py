from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime, timedelta, date, time

app = FastAPI(title="Smart Study Planner Demo", version="1.0")

# ----------------------------
# models
# ----------------------------

class StudentProfile(BaseModel):
    student_id: str
    major: str
    study_hours_per_week: int = Field(ge=0)
    preferred_study_times: List[str] = []

class Assignment(BaseModel):
    course_name: str
    assignment_title: str
    due_date: str  # iso string
    estimated_difficulty: str  # easy, medium, hard
    estimated_hours: int = Field(ge=0)

class TimeSlot(BaseModel):
    # one open time block
    scheduled_date: str
    start_time: str
    end_time: str

class GeneratePlanRequest(BaseModel):
    student_profile: StudentProfile
    assignments: List[Assignment]
    calendar_availability: List[TimeSlot]

class StudySession(BaseModel):
    course_name: str
    assignment_title: str
    scheduled_date: str
    start_time: str
    end_time: str
    priority_level: str

class StudyPlanResponse(BaseModel):
    plan_title: str
    weekly_overview: str
    study_sessions: List[StudySession]
    total_scheduled_hours: int
    llm_reasoning_summary: str


# ----------------------------
# helper functions
# ----------------------------

def parse_iso_date(d: str) -> date:
    # turn iso string into date
    return datetime.fromisoformat(d.replace("Z", "+00:00")).date()

def parse_hhmm(s: str) -> time:
    # turn hh:mm into time object
    return datetime.strptime(s, "%H:%M").time()

def minutes_between(start: str, end: str) -> int:
    # get minutes between two times
    st = datetime.strptime(start, "%H:%M")
    en = datetime.strptime(end, "%H:%M")
    return int((en - st).total_seconds() // 60)

def difficulty_weight(d: str) -> int:
    # give number based on difficulty
    d = d.lower().strip()
    return {"easy": 1, "medium": 2, "hard": 3}.get(d, 2)

def priority_label(days_until_due: int, diff: str) -> str:
    # decide priority based on due date and difficulty
    w = difficulty_weight(diff)
    if days_until_due <= 1:
        return "high"
    if days_until_due <= 3 and w >= 2:
        return "high"
    if days_until_due <= 7 or w == 3:
        return "medium"
    return "low"


# ----------------------------
# endpoints
# ----------------------------

class SyncCalendarRequest(BaseModel):
    token: str
    start_date: str
    end_date: str

@app.post("/sync-calendar")
def sync_calendar(req: SyncCalendarRequest):
    # fake calendar api
    # returns made up free time blocks

    start = datetime.strptime(req.start_date, "%Y-%m-%d").date()
    end = datetime.strptime(req.end_date, "%Y-%m-%d").date()

    availability: List[TimeSlot] = []
    d = start

    while d <= end:
        # weekdays get evening slots
        if d.weekday() < 5:
            availability.append(
                TimeSlot(
                    scheduled_date=str(d),
                    start_time="18:00",
                    end_time="20:00"
                )
            )
        # weekends get afternoon slots
        else:
            availability.append(
                TimeSlot(
                    scheduled_date=str(d),
                    start_time="13:00",
                    end_time="16:00"
                )
            )
        d += timedelta(days=1)

    return {"available_time_blocks": availability}


@app.post("/generate-plan", response_model=StudyPlanResponse)
def generate_plan(req: GeneratePlanRequest):
    # this makes the study schedule

    today = datetime.now().date()

    scored = []

    # score assignments
    for a in req.assignments:
        due = parse_iso_date(a.due_date)
        days_until = (due - today).days
        pr = priority_label(days_until, a.estimated_difficulty)

        score = (
            max(days_until, -999),
            -difficulty_weight(a.estimated_difficulty),
            -a.estimated_hours
        )

        scored.append((score, pr, due, a))

    # soonest due first
    scored.sort(key=lambda x: x[0])

    # break time blocks into 1 hour chunks
    chunks = []

    for slot in req.calendar_availability:
        mins = minutes_between(slot.start_time, slot.end_time)
        hours = mins // 60
        start_t = datetime.strptime(slot.start_time, "%H:%M")

        for i in range(hours):
            st = (start_t + timedelta(hours=i)).strftime("%H:%M")
            en = (start_t + timedelta(hours=i + 1)).strftime("%H:%M")
            chunks.append((slot.scheduled_date, st, en))

    sessions: List[StudySession] = []
    total_hours = 0

    # fill chunks with assignments
    for _, pr, due, a in scored:
        hours_left = a.estimated_hours

        while hours_left > 0 and chunks:
            d, st, en = chunks.pop(0)

            sessions.append(
                StudySession(
                    course_name=a.course_name,
                    assignment_title=a.assignment_title,
                    scheduled_date=d,
                    start_time=st,
                    end_time=en,
                    priority_level=pr
                )
            )

            hours_left -= 1
            total_hours += 1

    overview = (
        f"scheduled {total_hours} hour(s). "
        f"higher priority items placed first."
    )

    reasoning = (
        "assignments sorted by due date and difficulty. "
        "then placed into open time slots."
    )

    return StudyPlanResponse(
        plan_title="Weekly Smart Study Plan",
        weekly_overview=overview,
        study_sessions=sessions,
        total_scheduled_hours=total_hours,
        llm_reasoning_summary=reasoning
    )


@app.get("/progress")
def progress(student_id: str):
    # fake tracker api data

    return {
        "student_id": student_id,
        "completed_sessions": 3,
        "remaining_workload_hours_estimate": 6,
        "note": "demo data only"
    }
