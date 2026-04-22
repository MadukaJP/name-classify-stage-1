from fastapi import Query, Request, Response, APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import asc, desc, or_
from core.nlp.profile_filter_detector import detect_profile_filters
from models.profile import Profile
from pydantic_schemas.profile_create import ProfileCreate
from pydantic_schemas.profile_out import ProfileOut
from pydantic_schemas.profiles_out import ProfilesOut

import re
from sqlalchemy.sql import func
from datetime import datetime, timezone
from typing import Literal, Optional
from sqlalchemy.orm import Session
from database import get_db
from services.external_apis import all_external_data
from utils.country_utils import get_country_name_from_id
from utils.custom_content import custom_content
from utils.get_age_group import get_age_group

router = APIRouter()
NAME_REGEX = re.compile(r"^[A-Za-z\s\-']+$")
ALLOWED_SORT_BY = {"age", "created_at", "gender_probability"}
ALLOWED_ORDER = {"asc", "desc"}
ALLOWED_GENDERS = {"male", "female"}
ALLOWED_AGE_GROUPS = {"child", "teenager", "adult", "senior"}


@router.get("/")
def index():
    return {"message": "Welcome to Name Classify API"}


@router.post("/api/profiles")
async def create_profile(
    request: Request, profile: ProfileCreate, db: Session = Depends(get_db)
):

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

    profile_db = (
        db.query(Profile).filter(func.lower(Profile.name) == name.lower()).first()
    )

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

    # gender and sample size check
    if not gender:
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
    country_name = get_country_name_from_id(country_id)
    country_probability = most_likely_country["probability"]

    created_at = datetime.now(timezone.utc)

    profile_db = Profile(
        name=name,
        gender=gender,
        gender_probability=round(gender_probability, 2),
        age=age,
        age_group=age_group,
        country_id=country_id,
        country_name=country_name,
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

@router.get("/api/profiles/search")
def search_profiles(
    q: Optional[str] = None,
    sort_by: Optional[str] = "created_at",
    order: Optional[str] = "desc",
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    sort_by = (sort_by or "created_at").lower().strip()
    order = (order or "desc").lower().strip()

    if not q or not q.strip():
        return JSONResponse(
            status_code=400,
            content=custom_content(
                "error",
                message="Invalid query parameters",
            ),
        )

    if sort_by not in ALLOWED_SORT_BY or order not in ALLOWED_ORDER:
        return JSONResponse(
            status_code=400,
            content=custom_content(
                "error",
                message="Invalid query parameters",
            ),
        )

    filters = detect_profile_filters(q)

    min_age, max_age = filters.get("age_range", (None, None))
    age_groups = filters.get("age_group", [])
    genders = filters.get("genders", [])
    countries = filters.get("countries", [])
    names = filters.get("names", [])


    has_any_filter = any(
        value is not None and value != []
        for value in [min_age, max_age, age_groups, genders, countries, names]
    )

    if not has_any_filter:
        return JSONResponse(
            status_code=400,
            content=custom_content("error", message="Unable to interpret query"),
        )

    query = db.query(Profile)


    if genders:
        query = query.filter(func.lower(Profile.gender).in_([g.lower() for g in genders]))

    if countries:
        query = query.filter(func.lower(Profile.country_id).in_([c.lower() for c in countries]))

    if age_groups:
        query = query.filter(Profile.age_group.in_(age_groups))

    if min_age is not None:
        query = query.filter(Profile.age >= min_age)

    if max_age is not None:
        query = query.filter(Profile.age <= max_age)

    if names:
        name_filters = [Profile.name.ilike(f"%{name}%") for name in names]
        query = query.filter(or_(*name_filters))


    # Sorting
    sort_column_map = {
        "age": Profile.age,
        "created_at": Profile.created_at,
        "gender_probability": Profile.gender_probability,
    }

    sort_column = sort_column_map.get(sort_by, Profile.created_at)

    query = query.order_by(desc(sort_column) if order == "desc" else asc(sort_column))


    # Pagination
    total = query.count()
    offset = (page - 1) * limit
    profiles = query.offset(offset).limit(limit).all()

    data = [ProfilesOut.model_validate(p).model_dump(mode="json") for p in profiles]

    return JSONResponse(
        status_code=200,
        content=custom_content(
            "success",
            page=page,
            limit=limit,
            total=total,
            data=data,
        ),
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
def get_profiles(
    gender: Optional[str] = None,
    country_id: Optional[str] = None,
    age_group: Optional[str] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    min_gender_probability: Optional[float] = None,
    min_country_probability: Optional[float] = None,
    # Sorting
    sort_by: Optional[str] = "created_at",
    order: Optional[str] = "desc",
    # Pagination
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):

    try:
        if gender:
            gender = gender.lower().strip()
        if age_group:
            age_group = age_group.lower().strip()
        if sort_by:
            sort_by = sort_by.lower().strip()
        if order:
            order = order.lower().strip()

        # Validate Page & Limit
        page = int(page)
        limit = int(limit)
        if page < 1 or limit < 1 or limit > 50:
            raise ValueError()

        # Validate Age Group
        allowed_groups = ["child", "teenager", "adult", "senior"]
        if age_group and age_group not in allowed_groups:
            raise ValueError()

        # Validate Gender
        if gender and gender.lower() not in ALLOWED_GENDERS:
            raise ValueError()

        # Validate Sorting & Ordering
        if sort_by not in ALLOWED_SORT_BY:
            raise ValueError()
        if order not in ALLOWED_ORDER:
            raise ValueError()
 

        if min_age is not None:
            min_age = int(min_age)
        if max_age is not None:
            max_age = int(max_age)
        if min_gender_probability is not None:
            min_gender_probability = float(min_gender_probability)
        if min_country_probability is not None:
            min_country_probability = float(min_country_probability)

    except (ValueError, TypeError) as e:
        print (e)
        return JSONResponse(
            status_code=400,
            content=custom_content("error", message="Invalid query parameters"),
        )

    query = db.query(Profile)

    if gender:
        query = query.filter(func.lower(Profile.gender) == gender.lower())
    if country_id:
        query = query.filter(func.lower(Profile.country_id) == country_id.lower())
    if age_group:
        query = query.filter(Profile.age_group == age_group.lower())

    if min_age is not None:
        query = query.filter(Profile.age >= min_age)
    if max_age is not None:
        query = query.filter(Profile.age <= max_age)
    if min_gender_probability is not None:
        query = query.filter(Profile.gender_probability >= min_gender_probability)
    if min_country_probability is not None:
        query = query.filter(Profile.country_probability >= min_country_probability)

    # Sorting & Pagination
    sort_column = getattr(Profile, sort_by or "created_at")
    query = query.order_by(desc(sort_column) if order == "desc" else asc(sort_column))

    total_count = query.count()
    offset = (page - 1) * limit
    profiles = query.offset(offset).limit(limit).all()

    data = [ProfilesOut.model_validate(p).model_dump(mode="json") for p in profiles]

    return JSONResponse(
        status_code=200,
        content=custom_content(
            "success", page=page, limit=limit, total=total_count, data=data
        ),
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
