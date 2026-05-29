"""Production-ready FastAPI backend for AI Fitness Coach MVP.

Provides authentication-aware onboarding, plan generation, progress tracking,
analytics capture, and health endpoints. Integrates with Supabase, Clerk JWTs,
OpenAI-compatible chat APIs, and PostHog when environment variables are present;
falls back to deterministic local generation where safe so the app remains
runnable in local development.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import Depends, FastAPI, Header, HTTPException, Request as FastAPIRequest, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

try:
    from supabase import Client as SupabaseClient
    from supabase import create_client
except Exception:  # pragma: no cover - optional dependency for local smoke tests
    SupabaseClient = Any  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]

try:
    from jose import jwt
    from jose.exceptions import JOSEError
except Exception:  # pragma: no cover - optional dependency for local smoke tests
    jwt = None  # type: ignore[assignment]
    JOSEError = Exception  # type: ignore[assignment]

try:
    import posthog
except Exception:  # pragma: no cover - optional dependency for local smoke tests
    posthog = None  # type: ignore[assignment]


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("ai_fitness_coach")


class Settings(BaseModel):
    app_name: str = "AI Fitness Coach API"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    allowed_origins: list[str] = Field(default_factory=list)
    supabase_url: str | None = Field(default_factory=lambda: os.getenv("SUPABASE_URL"))
    supabase_service_role_key: str | None = Field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY"))
    clerk_jwks_url: str | None = Field(default_factory=lambda: os.getenv("CLERK_JWKS_URL"))
    clerk_secret_key: str | None = Field(default_factory=lambda: os.getenv("CLERK_SECRET_KEY"))
    clerk_jwt_issuer: str | None = Field(default_factory=lambda: os.getenv("CLERK_JWT_ISSUER"))
    openai_api_key: str | None = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    openai_base_url: str = Field(default_factory=lambda: os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    posthog_api_key: str | None = Field(default_factory=lambda: os.getenv("POSTHOG_API_KEY"))
    posthog_host: str = Field(default_factory=lambda: os.getenv("POSTHOG_HOST", "https://us.i.posthog.com"))
    auth_optional: bool = Field(default_factory=lambda: os.getenv("AUTH_OPTIONAL", "true").lower() == "true")
    request_timeout_seconds: int = Field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")))

    @model_validator(mode="after")
    def normalize_origins(self) -> "Settings":
        raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        self.allowed_origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        return self


settings = Settings()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Backend API for personalized workout, nutrition, onboarding, and progress tracking.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ActivityLevel(str, Enum):
    sedentary = "sedentary"
    lightly_active = "lightly_active"
    moderately_active = "moderately_active"
    very_active = "very_active"
    athlete = "athlete"


class FitnessGoal(str, Enum):
    fat_loss = "fat_loss"
    muscle_gain = "muscle_gain"
    endurance = "endurance"
    strength = "strength"
    general_health = "general_health"
    mobility = "mobility"


class DietaryPreference(str, Enum):
    balanced = "balanced"
    vegetarian = "vegetarian"
    vegan = "vegan"
    pescatarian = "pescatarian"
    keto = "keto"
    mediterranean = "mediterranean"
    high_protein = "high_protein"


class UserContext(BaseModel):
    user_id: str
    claims: dict[str, Any] = Field(default_factory=dict)
    authenticated: bool = False


class BiometricProfile(BaseModel):
    age: int = Field(ge=18, le=80)
    weight_kg: float = Field(gt=35, lt=250)
    height_cm: float = Field(gt=120, lt=230)
    sex: Literal["male", "female", "other"] = "other"
    activity_level: ActivityLevel
    goals: list[FitnessGoal] = Field(min_length=1, max_length=3)
    dietary_preference: DietaryPreference = DietaryPreference.balanced
    allergies: list[str] = Field(default_factory=list, max_length=20)
    injuries: list[str] = Field(default_factory=list, max_length=20)
    workout_days_per_week: int = Field(default=4, ge=2, le=7)
    workout_minutes: int = Field(default=45, ge=20, le=120)
    equipment: list[str] = Field(default_factory=lambda: ["bodyweight"], max_length=20)
    sleep_hours: float | None = Field(default=None, ge=3, le=12)
    stress_level: int | None = Field(default=None, ge=1, le=10)

    @field_validator("allergies", "injuries", "equipment")
    @classmethod
    def sanitize_terms(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            normalized = re.sub(r"\s+", " ", item.strip())[:80]
            if normalized and normalized.lower() not in {entry.lower() for entry in cleaned}:
                cleaned.append(normalized)
        return cleaned


class OnboardingRequest(BiometricProfile):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)


class PlanRequest(BaseModel):
    profile: BiometricProfile
    focus: Literal["workout", "nutrition", "complete"] = "complete"


class Exercise(BaseModel):
    name: str
    sets: int = Field(ge=1, le=10)
    reps: str
    rest_seconds: int = Field(ge=15, le=300)
    notes: str


class WorkoutDay(BaseModel):
    day: int
    title: str
    duration_minutes: int
    warmup: list[str]
    exercises: list[Exercise]
    cooldown: list[str]


class WorkoutPlan(BaseModel):
    summary: str
    weekly_schedule: list[WorkoutDay]
    progression: str
    safety_notes: list[str]


class Meal(BaseModel):
    name: str
    calories: int = Field(ge=100, le=1500)
    protein_g: int = Field(ge=0, le=200)
    carbs_g: int = Field(ge=0, le=250)
    fat_g: int = Field(ge=0, le=150)
    ingredients: list[str]


class NutritionPlan(BaseModel):
    summary: str
    daily_calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    meals: list[Meal]
    hydration_liters: float
    guidance: list[str]


class CompletePlan(BaseModel):
    workout: WorkoutPlan | None = None
    nutrition: NutritionPlan | None = None
    generated_at: datetime
    source: Literal["ai", "local"]


class ProgressEntry(BaseModel):
    entry_date: date = Field(default_factory=date.today)
    weight_kg: float | None = Field(default=None, gt=35, lt=250)
    body_fat_percent: float | None = Field(default=None, ge=3, le=70)
    resting_heart_rate: int | None = Field(default=None, ge=35, le=140)
    workout_completed: bool = False
    calories_consumed: int | None = Field(default=None, ge=800, le=8000)
    protein_g: int | None = Field(default=None, ge=0, le=400)
    notes: str | None = Field(default=None, max_length=1000)


class ProgressSummary(BaseModel):
    entries: list[ProgressEntry]
    latest: ProgressEntry | None
    trend: dict[str, Any]


class AnalyticsEvent(BaseModel):
    event: str = Field(min_length=1, max_length=120)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event")
    @classmethod
    def validate_event_name(cls, value: str) -> str:
        event = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", event):
            raise ValueError("event must contain only letters, numbers, underscores, dots, colons, or hyphens")
        return event


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    services: dict[str, bool]
    timestamp: datetime


_supabase: SupabaseClient | None = None
_jwks_cache: dict[str, Any] = {"expires_at": 0, "keys": []}
_memory_profiles: dict[str, dict[str, Any]] = {}
_memory_progress: dict[str, list[dict[str, Any]]] = {}


@app.on_event("startup")
def configure_integrations() -> None:
    global _supabase
    if create_client and settings.supabase_url and settings.supabase_service_role_key:
        _supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    if posthog and settings.posthog_api_key:
        posthog.project_api_key = settings.posthog_api_key
        posthog.host = settings.posthog_host


def _json_request(url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers or {}, method="GET" if payload is None else "POST")
    try:
        with urlopen(request, timeout=settings.request_timeout_seconds) as response:  # nosec B310 - URLs come from trusted env configuration
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Upstream API error: {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Upstream API unavailable") from exc


def _get_jwks() -> list[dict[str, Any]]:
    if not settings.clerk_jwks_url:
        return []
    now = time.time()
    if _jwks_cache["expires_at"] > now:
        return list(_jwks_cache["keys"])
    data = _json_request(settings.clerk_jwks_url)
    keys = data.get("keys", [])
    _jwks_cache.update({"expires_at": now + 3600, "keys": keys})
    return list(keys)


def _decode_unverified_subject(token: str) -> str:
    try:
        payload_segment = token.split(".")[1]
        padded = payload_segment + "=" * (-len(payload_segment) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")))
        subject = str(payload.get("sub") or "")
        if subject:
            return subject
    except Exception:
        pass
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    return f"token_{digest}"


def _verify_clerk_token(token: str) -> UserContext:
    if jwt and settings.clerk_jwks_url:
        try:
            header = jwt.get_unverified_header(token)
            key = next((candidate for candidate in _get_jwks() if candidate.get("kid") == header.get("kid")), None)
            if not key:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT signing key not found")
            options = {"verify_aud": False}
            claims = jwt.decode(token, key, algorithms=[key.get("alg", "RS256")], issuer=settings.clerk_jwt_issuer, options=options)
            return UserContext(user_id=str(claims["sub"]), claims=claims, authenticated=True)
        except HTTPException:
            raise
        except JOSEError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc
    if settings.environment == "production" and not settings.auth_optional:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Clerk JWT verification is not configured")
    return UserContext(user_id=_decode_unverified_subject(token), claims={}, authenticated=False)


def _anonymous_user_id(request: FastAPIRequest) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    host = forwarded_for or (request.client.host if request.client else "local")
    user_agent = request.headers.get("user-agent", "unknown")[:200]
    digest = hmac.new(b"ai-fitness-coach", f"{host}:{user_agent}".encode("utf-8"), hashlib.sha256).hexdigest()[:24]
    return f"anon_{digest}"


async def get_current_user(
    request: FastAPIRequest,
    authorization: str | None = Header(default=None),
) -> UserContext:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header must use Bearer token")
        return _verify_clerk_token(token)
    if not settings.auth_optional:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return UserContext(user_id=_anonymous_user_id(request), authenticated=False)


def _profile_key(user: UserContext) -> str:
    return user.user_id


def _bmr(profile: BiometricProfile) -> float:
    base = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age
    if profile.sex == "male":
        return base + 5
    if profile.sex == "female":
        return base - 161
    return base - 78


def _activity_multiplier(level: ActivityLevel) -> float:
    return {
        ActivityLevel.sedentary: 1.2,
        ActivityLevel.lightly_active: 1.375,
        ActivityLevel.moderately_active: 1.55,
        ActivityLevel.very_active: 1.725,
        ActivityLevel.athlete: 1.9,
    }[level]


def _calorie_target(profile: BiometricProfile) -> int:
    maintenance = _bmr(profile) * _activity_multiplier(profile.activity_level)
    goals = set(profile.goals)
    if FitnessGoal.fat_loss in goals:
        maintenance -= 400
    if FitnessGoal.muscle_gain in goals or FitnessGoal.strength in goals:
        maintenance += 250
    return max(1400, min(4200, round(maintenance / 25) * 25))


def _macro_targets(profile: BiometricProfile, calories: int) -> tuple[int, int, int]:
    protein_multiplier = 2.0 if FitnessGoal.muscle_gain in profile.goals or FitnessGoal.strength in profile.goals else 1.7
    protein = round(profile.weight_kg * protein_multiplier)
    fat = round((calories * 0.28) / 9)
    carbs = max(50, round((calories - protein * 4 - fat * 9) / 4))
    if profile.dietary_preference == DietaryPreference.keto:
        carbs = min(carbs, 50)
        fat = round((calories - protein * 4 - carbs * 4) / 9)
    return protein, carbs, fat


def _generate_local_workout(profile: BiometricProfile) -> WorkoutPlan:
    equipment = {item.lower() for item in profile.equipment} or {"bodyweight"}
    injury_note = f"Avoid movements that aggravate: {', '.join(profile.injuries)}." if profile.injuries else "Keep all reps pain-free with controlled tempo."
    strength_bias = FitnessGoal.strength in profile.goals or FitnessGoal.muscle_gain in profile.goals
    endurance_bias = FitnessGoal.endurance in profile.goals or FitnessGoal.fat_loss in profile.goals

    templates: list[tuple[str, list[Exercise]]] = [
        (
            "Full-body strength",
            [
                Exercise(name="Goblet squat" if "dumbbells" in equipment else "Tempo bodyweight squat", sets=4, reps="8-12", rest_seconds=90, notes="Brace core and drive knees over toes."),
                Exercise(name="Dumbbell row" if "dumbbells" in equipment else "Inverted row or towel row", sets=3, reps="10-12/side", rest_seconds=75, notes="Pull elbows toward hips."),
                Exercise(name="Push-up", sets=3, reps="8-15", rest_seconds=75, notes="Elevate hands if needed to keep form strict."),
                Exercise(name="Romanian deadlift" if "dumbbells" in equipment else "Single-leg hip hinge", sets=3, reps="10-12", rest_seconds=75, notes="Hips back, neutral spine."),
            ],
        ),
        (
            "Metabolic conditioning",
            [
                Exercise(name="Reverse lunge", sets=3, reps="10/side", rest_seconds=45, notes="Step back softly and keep torso tall."),
                Exercise(name="Mountain climber", sets=4, reps="30 seconds", rest_seconds=30, notes="Fast feet, stable shoulders."),
                Exercise(name="Kettlebell swing" if "kettlebell" in equipment else "Glute bridge march", sets=4, reps="12-20", rest_seconds=45, notes="Explosive hip extension."),
                Exercise(name="Plank", sets=3, reps="40-60 seconds", rest_seconds=45, notes="Ribs down, glutes tight."),
            ],
        ),
        (
            "Upper-body and core",
            [
                Exercise(name="Overhead press" if "dumbbells" in equipment else "Pike push-up", sets=4, reps="8-12", rest_seconds=90, notes="Finish biceps by ears."),
                Exercise(name="Lat pulldown" if "gym" in equipment else "Band pulldown", sets=3, reps="10-15", rest_seconds=75, notes="Depress shoulder blades before pulling."),
                Exercise(name="Floor press" if "dumbbells" in equipment else "Close-grip push-up", sets=3, reps="8-12", rest_seconds=75, notes="Keep wrists stacked over elbows."),
                Exercise(name="Dead bug", sets=3, reps="8/side", rest_seconds=45, notes="Low back stays on floor."),
            ],
        ),
        (
            "Lower-body power",
            [
                Exercise(name="Front squat" if "gym" in equipment else "Split squat", sets=4, reps="6-10", rest_seconds=120, notes="Use challenging load with clean reps."),
                Exercise(name="Hip thrust", sets=4, reps="10-12", rest_seconds=90, notes="Pause one second at top."),
                Exercise(name="Step-up", sets=3, reps="10/side", rest_seconds=75, notes="Drive through full foot."),
                Exercise(name="Farmer carry" if "dumbbells" in equipment or "kettlebell" in equipment else "Wall sit", sets=3, reps="45 seconds", rest_seconds=60, notes="Tall posture and steady breathing."),
            ],
        ),
    ]

    schedule: list[WorkoutDay] = []
    for index in range(profile.workout_days_per_week):
        title, exercises = templates[index % len(templates)]
        if endurance_bias and index == profile.workout_days_per_week - 1:
            title = "Zone 2 cardio and mobility"
            exercises = [
                Exercise(name="Zone 2 cardio", sets=1, reps=f"{max(20, profile.workout_minutes - 15)} minutes", rest_seconds=30, notes="Conversational pace."),
                Exercise(name="Hip mobility flow", sets=2, reps="6 minutes", rest_seconds=30, notes="Move slowly through full range."),
                Exercise(name="Thoracic rotations", sets=2, reps="8/side", rest_seconds=30, notes="Exhale into each rotation."),
            ]
        if strength_bias and index == 0:
            exercises[0].sets = min(5, exercises[0].sets + 1)
            exercises[0].rest_seconds = min(150, exercises[0].rest_seconds + 30)
        schedule.append(
            WorkoutDay(
                day=index + 1,
                title=title,
                duration_minutes=profile.workout_minutes,
                warmup=["5 minutes easy cardio", "Dynamic hips and shoulders", "Two ramp-up sets for first lift"],
                exercises=exercises,
                cooldown=["3 minutes nasal breathing", "Hamstring stretch", "Chest opener"],
            )
        )

    return WorkoutPlan(
        summary=f"{profile.workout_days_per_week}-day plan built for {', '.join(goal.value.replace('_', ' ') for goal in profile.goals)} with {profile.workout_minutes}-minute sessions.",
        weekly_schedule=schedule,
        progression="Add 1-2 reps each week until top of rep range, then increase load 2-5% and return to lower range.",
        safety_notes=[injury_note, "Stop sets with 1-2 reps in reserve unless coached otherwise.", "Take an extra rest day if sleep drops below 6 hours for two consecutive nights."],
    )


def _meal_templates(preference: DietaryPreference, calories: int, protein: int, carbs: int, fat: int) -> list[Meal]:
    vegan = preference == DietaryPreference.vegan
    vegetarian = preference in {DietaryPreference.vegetarian, DietaryPreference.vegan}
    keto = preference == DietaryPreference.keto
    return [
        Meal(
            name="Protein breakfast bowl",
            calories=round(calories * 0.27),
            protein_g=round(protein * 0.28),
            carbs_g=round(carbs * (0.15 if keto else 0.28)),
            fat_g=round(fat * 0.30),
            ingredients=["tofu scramble" if vegan else "Greek yogurt" if vegetarian else "eggs", "berries" if not keto else "avocado", "chia seeds", "spinach"],
        ),
        Meal(
            name="Power lunch plate",
            calories=round(calories * 0.34),
            protein_g=round(protein * 0.35),
            carbs_g=round(carbs * (0.20 if keto else 0.36)),
            fat_g=round(fat * 0.32),
            ingredients=["tempeh" if vegan else "lentils and eggs" if vegetarian else "grilled chicken", "quinoa" if not keto else "cauliflower rice", "mixed greens", "olive oil dressing"],
        ),
        Meal(
            name="Recovery dinner",
            calories=round(calories * 0.31),
            protein_g=round(protein * 0.30),
            carbs_g=round(carbs * (0.25 if keto else 0.30)),
            fat_g=round(fat * 0.30),
            ingredients=["seitan" if vegan else "paneer" if vegetarian else "salmon", "sweet potato" if not keto else "zucchini noodles", "broccoli", "herbs"],
        ),
        Meal(
            name="Smart snack",
            calories=max(150, calories - round(calories * 0.92)),
            protein_g=max(10, protein - round(protein * 0.93)),
            carbs_g=max(5, carbs - round(carbs * (0.60 if keto else 0.94))),
            fat_g=max(5, fat - round(fat * 0.92)),
            ingredients=["protein shake" if not vegan else "pea protein shake", "almonds", "fruit" if not keto else "celery"],
        ),
    ]


def _generate_local_nutrition(profile: BiometricProfile) -> NutritionPlan:
    calories = _calorie_target(profile)
    protein, carbs, fat = _macro_targets(profile, calories)
    allergy_note = f"Avoid allergens: {', '.join(profile.allergies)}." if profile.allergies else "Rotate protein and produce sources weekly for micronutrient variety."
    return NutritionPlan(
        summary=f"{profile.dietary_preference.value.replace('_', ' ')} nutrition target aligned to {', '.join(goal.value.replace('_', ' ') for goal in profile.goals)}.",
        daily_calories=calories,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
        meals=_meal_templates(profile.dietary_preference, calories, protein, carbs, fat),
        hydration_liters=round(max(2.0, profile.weight_kg * 0.035), 1),
        guidance=[allergy_note, "Prep two proteins and two carbohydrates twice weekly to reduce decision fatigue.", "Anchor each meal with 25-45g protein and one serving of colorful plants."],
    )


def _ai_plan(profile: BiometricProfile, focus: str) -> CompletePlan | None:
    if not settings.openai_api_key:
        return None
    prompt = (
        "Create a safe, evidence-informed fitness coaching plan as strict JSON matching this schema: "
        "{workout:{summary,weekly_schedule:[{day,title,duration_minutes,warmup,exercises:[{name,sets,reps,rest_seconds,notes}],cooldown}],progression,safety_notes},"
        "nutrition:{summary,daily_calories,protein_g,carbs_g,fat_g,meals:[{name,calories,protein_g,carbs_g,fat_g,ingredients}],hydration_liters,guidance}}. "
        f"Focus: {focus}. Profile: {profile.model_dump_json()}."
    )
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "You are a certified fitness and nutrition coach. Return JSON only. Avoid medical claims. Include injury-aware safety guidance."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.35,
        "response_format": {"type": "json_object"},
    }
    try:
        data = _json_request(
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            payload,
            {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
        )
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return CompletePlan(
            workout=WorkoutPlan.model_validate(parsed.get("workout")) if focus in {"workout", "complete"} and parsed.get("workout") else None,
            nutrition=NutritionPlan.model_validate(parsed.get("nutrition")) if focus in {"nutrition", "complete"} and parsed.get("nutrition") else None,
            generated_at=datetime.now(timezone.utc),
            source="ai",
        )
    except Exception as exc:
        logger.warning("AI generation failed; falling back to local plan: %s", exc)
        return None


def _build_plan(profile: BiometricProfile, focus: str = "complete") -> CompletePlan:
    ai_generated = _ai_plan(profile, focus)
    if ai_generated:
        return ai_generated
    return CompletePlan(
        workout=_generate_local_workout(profile) if focus in {"workout", "complete"} else None,
        nutrition=_generate_local_nutrition(profile) if focus in {"nutrition", "complete"} else None,
        generated_at=datetime.now(timezone.utc),
        source="local",
    )


def _persist_profile(user: UserContext, payload: dict[str, Any]) -> dict[str, Any]:
    key = _profile_key(user)
    record = {"user_id": key, "profile": payload, "updated_at": datetime.now(timezone.utc).isoformat()}
    _memory_profiles[key] = record
    if _supabase:
        try:
            _supabase.table("profiles").upsert(record, on_conflict="user_id").execute()
        except Exception as exc:
            logger.warning("Supabase profile upsert failed: %s", exc)
    return record


def _load_profile(user: UserContext) -> dict[str, Any] | None:
    key = _profile_key(user)
    if _supabase:
        try:
            response = _supabase.table("profiles").select("*").eq("user_id", key).limit(1).execute()
            if response.data:
                return response.data[0]
        except Exception as exc:
            logger.warning("Supabase profile fetch failed: %s", exc)
    return _memory_profiles.get(key)


def _persist_progress(user: UserContext, entry: ProgressEntry) -> dict[str, Any]:
    key = _profile_key(user)
    record = {"user_id": key, **entry.model_dump(mode="json"), "created_at": datetime.now(timezone.utc).isoformat()}
    _memory_progress.setdefault(key, []).append(record)
    if _supabase:
        try:
            _supabase.table("progress_entries").insert(record).execute()
        except Exception as exc:
            logger.warning("Supabase progress insert failed: %s", exc)
    return record


def _load_progress(user: UserContext, limit: int) -> list[dict[str, Any]]:
    key = _profile_key(user)
    if _supabase:
        try:
            response = _supabase.table("progress_entries").select("*").eq("user_id", key).order("entry_date", desc=True).limit(limit).execute()
            return list(response.data or [])
        except Exception as exc:
            logger.warning("Supabase progress fetch failed: %s", exc)
    return sorted(_memory_progress.get(key, []), key=lambda item: item.get("entry_date", ""), reverse=True)[:limit]


def _capture(user: UserContext, event: str, properties: dict[str, Any] | None = None) -> None:
    safe_properties = dict(properties or {})
    safe_properties.update({"authenticated": user.authenticated, "environment": settings.environment})
    if posthog and settings.posthog_api_key:
        try:
            posthog.capture(user.user_id, event, safe_properties)
        except Exception as exc:
            logger.warning("PostHog capture failed: %s", exc)


def _progress_trend(entries: list[ProgressEntry]) -> dict[str, Any]:
    chronological = sorted(entries, key=lambda item: item.entry_date)
    weights = [entry.weight_kg for entry in chronological if entry.weight_kg is not None]
    workouts = sum(1 for entry in entries if entry.workout_completed)
    trend: dict[str, Any] = {"workouts_completed": workouts, "entry_count": len(entries)}
    if len(weights) >= 2:
        trend["weight_change_kg"] = round(weights[-1] - weights[0], 2)
    if chronological:
        trend["latest_entry_date"] = chronological[-1].entry_date.isoformat()
    return trend


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        services={
            "supabase": bool(_supabase),
            "clerk": bool(settings.clerk_jwks_url),
            "openai": bool(settings.openai_api_key),
            "posthog": bool(settings.posthog_api_key),
        },
        timestamp=datetime.now(timezone.utc),
    )


@app.post("/onboarding", response_model=dict[str, Any])
def save_onboarding(payload: OnboardingRequest, user: UserContext = Depends(get_current_user)) -> dict[str, Any]:
    profile_data = payload.model_dump(mode="json")
    record = _persist_profile(user, profile_data)
    _capture(user, "onboarding_completed", {"goals": [goal.value for goal in payload.goals], "activity_level": payload.activity_level.value})
    return {"profile": record, "plan_preview": _build_plan(payload, "complete")}


@app.get("/profile", response_model=dict[str, Any])
def get_profile(user: UserContext = Depends(get_current_user)) -> dict[str, Any]:
    record = _load_profile(user)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return record


@app.post("/plans/generate", response_model=CompletePlan)
def generate_plan(payload: PlanRequest, user: UserContext = Depends(get_current_user)) -> CompletePlan:
    plan = _build_plan(payload.profile, payload.focus)
    _capture(user, "plan_generated", {"focus": payload.focus, "source": plan.source})
    return plan


@app.get("/plans/current", response_model=CompletePlan)
def current_plan(user: UserContext = Depends(get_current_user)) -> CompletePlan:
    record = _load_profile(user)
    if not record or not record.get("profile"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    profile = BiometricProfile.model_validate(record["profile"])
    return _build_plan(profile, "complete")


@app.post("/progress", response_model=dict[str, Any])
def add_progress(entry: ProgressEntry, user: UserContext = Depends(get_current_user)) -> dict[str, Any]:
    record = _persist_progress(user, entry)
    _capture(user, "progress_logged", {"workout_completed": entry.workout_completed, "has_weight": entry.weight_kg is not None})
    return record


@app.get("/progress", response_model=ProgressSummary)
def list_progress(limit: int = 30, user: UserContext = Depends(get_current_user)) -> ProgressSummary:
    safe_limit = max(1, min(limit, 180))
    records = _load_progress(user, safe_limit)
    entries = [ProgressEntry.model_validate(record) for record in records]
    latest = sorted(entries, key=lambda item: item.entry_date, reverse=True)[0] if entries else None
    return ProgressSummary(entries=entries, latest=latest, trend=_progress_trend(entries))


@app.post("/analytics", response_model=dict[str, str])
def analytics(event: AnalyticsEvent, user: UserContext = Depends(get_current_user)) -> dict[str, str]:
    _capture(user, event.event, event.properties)
    return {"status": "captured"}


@app.get("/recommendations/today", response_model=dict[str, Any])
def today_recommendations(user: UserContext = Depends(get_current_user)) -> dict[str, Any]:
    record = _load_profile(user)
    if not record or not record.get("profile"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    profile = BiometricProfile.model_validate(record["profile"])
    progress_records = _load_progress(user, 7)
    recent_entries = [ProgressEntry.model_validate(item) for item in progress_records]
    completed_recently = sum(1 for item in recent_entries if item.workout_completed)
    plan = _build_plan(profile, "complete")
    next_workout = plan.workout.weekly_schedule[completed_recently % len(plan.workout.weekly_schedule)] if plan.workout and plan.workout.weekly_schedule else None
    recovery_flag = bool(profile.sleep_hours and profile.sleep_hours < 6) or bool(profile.stress_level and profile.stress_level >= 8)
    return {
        "date": date.today().isoformat(),
        "next_workout": next_workout,
        "nutrition_target": plan.nutrition,
        "coaching_tip": "Reduce intensity by 20% and prioritize sleep tonight." if recovery_flag else "Hit protein target early and complete workout before peak work fatigue.",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")), reload=settings.environment == "development")
