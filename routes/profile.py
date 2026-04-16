from fastapi import Request, Response, APIRouter, Depends
from fastapi.responses import JSONResponse
from models.profile import Profile
from pydantic_schemas.profile_create import ProfileCreate
from pydantic_schemas.profile_out import ProfileOut
from pydantic_schemas.profiles_out import ProfilesOut

import re
from sqlalchemy.sql import func
from datetime import datetime, timezone
from typing import Literal
from sqlalchemy.orm import Session
from database import get_db
from services.external_apis import all_external_data
from utils.custom_content import custom_content
from utils.get_age_group import get_age_group

router = APIRouter()
NAME_REGEX = re.compile(r"^[A-Za-z\s\-']+$")

@router.get("/")
def index():
    return {"message": "Welcome to Name Classify API"}


@router.post("/api/profiles")
async def create_profile(request: Request, profile: ProfileCreate, db: Session = Depends(get_db)):

    name = profile.name.strip()

    if name.strip() == "":
        return JSONResponse(
            status_code=400,
            content=custom_content(
                "error", message="Bad Request: Missing or empty name"
            ),
        )

    # regex string validation
    if not NAME_REGEX.fullmatch(name):
        return JSONResponse(
            status_code=422,
            content=custom_content(
                "error", message="Unprocessable Entity: Invalid type"
            ),
        )

    profile_db = db.query(Profile).filter(func.lower(Profile.name) == name.lower()).first()

    if profile_db:
        profile_response = ProfileOut.model_validate(profile_db).model_dump()
        return JSONResponse(
            status_code=200,
            content=custom_content(
                "success", message="Profile already exists", data=profile_response
            ),
        )


    # fetch data
    external_result = await all_external_data(request, name)

    if external_result.get("error"):
        return JSONResponse(
            status_code=502,
            content=custom_content(
                "error",
                message=external_result.get("message", "Upstream or server failure"),
            ),
        )

    data = external_result["data"]

    # get data categories
    genderize = data["genderize"]
    agify = data["agify"]
    nationalize = data["nationalize"]

    # extract gender details
    gender = genderize.get("gender")
    gender_probability = genderize.get("probability", 0)
    sample_size = genderize.get("count", 0)

    # gender and sample size check
    if not gender or sample_size == 0:
        return JSONResponse(
            status_code=502,
            content=custom_content(
                "error", message="Genderize returned an invalid response"
            ),
        )

    # extract age details
    age = agify.get("age")
    if age is None:
        return JSONResponse(
            status_code=502,
            content=custom_content(
                "error", message="Agify returned an invalid response"
            ),
        )

    age_group = get_age_group(age)

    # extract nationality details
    countries = nationalize.get("country", [])

    if not countries:
        return JSONResponse(
            status_code=502,
            content=custom_content(
                "error", message="Nationalize returned an invalid response"
            ),
        )

    most_likely_country = max(countries, key=lambda x: x["probability"])
    country_id = most_likely_country["country_id"]
    country_probability = most_likely_country["probability"]

    created_at = datetime.now(timezone.utc)

    profile_db = Profile(
        name=name,
        gender=gender,
        gender_probability=round(gender_probability, 2),
        sample_size=sample_size,
        age=age,
        age_group=age_group,
        country_id=country_id,
        country_probability=round(country_probability, 2),
        created_at=created_at,
    )

    db.add(profile_db)
    db.commit()
    db.refresh(profile_db)

    profile_response = ProfileOut.model_validate(profile_db).model_dump()

    return JSONResponse(
        status_code=201, content=custom_content("success", data=profile_response)
    )


@router.get("/api/profiles/{id}")
def get_profile(id: str | None = None, db: Session = Depends(get_db)):
    if not id:
        return JSONResponse(
            status_code=400,
            content=custom_content("error", message="Bad Request: Missing or empty id"),
        )

    profile_db = db.query(Profile).filter(Profile.id == id).first()

    if not profile_db:
        return JSONResponse(
            status_code=404,
            content=custom_content(
                "error",
                message="Profile not found",
            ),
        )

    profile_response = ProfileOut.model_validate(profile_db).model_dump()

    return JSONResponse(
        status_code=200, content=custom_content("success", data=profile_response)
    )


@router.get("/api/profiles")
def get_profile(
    gender: str | None = None,
    country_id: str | None = None,
    age_group: Literal["child", "teenager", "adult", "senior"] | None = None,
    db: Session = Depends(get_db)
):

    query = db.query(Profile)

    if gender is not None:
        query = query.filter(func.lower(Profile.gender) == gender.lower())

    if country_id is not None:
        query = query.filter(func.lower(Profile.country_id) == country_id.lower())

    if age_group is not None:
        query = query.filter(Profile.age_group == age_group)

    profiles = query.all()

    serialized_profiles = [
        ProfilesOut.model_validate(profile).model_dump() for profile in profiles
    ]

    count = len(serialized_profiles)

    return JSONResponse(
        status_code=200,
        content=custom_content("success", count=count, data=serialized_profiles),
    )


@router.delete("/api/profiles/{id}")
def delete_profile(id: str, db: Session = Depends(get_db)):
    profile_db = db.query(Profile).filter(Profile.id == id).first()

    if not profile_db:
        return JSONResponse(
            status_code=404,
            content=custom_content(
                "error",
                message="Profile not found",
            ),
        )
    
    db.delete(profile_db)
    db.commit()

    return Response(status_code=204)
