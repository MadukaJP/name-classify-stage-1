import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database import SessionLocal
from models.profile import Profile
from utils.country_utils import get_country_name_from_id
from utils.get_age_group import get_age_group

NAME_REGEX = re.compile(r"^[A-Za-zÀ-ÿ\s'-]{2,100}$")


def normalize_text(value: str):
    if not value:
        return value
    return unicodedata.normalize("NFKC", value).strip()


def clamp_prob(x):
    if x is None:
        return 0.0
    try:
        x = float(x)
        return max(0.0, min(1.0, x))
    except Exception:
        return 0.0


def seed_profiles():
    db = SessionLocal()
    seed_path = ROOT_DIR / "data" / "seed_profiles.json"

    with seed_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    inserted = 0
    skipped = 0
    existing_names = {
        name.lower()
        for (name,) in db.query(Profile.name).all()
        if name is not None
    }

    try:
        for item in data.get("profiles", []):
            name = normalize_text(item.get("name"))

            if not name or not NAME_REGEX.fullmatch(name):
                skipped += 1
                continue

            age = item.get("age")
            gender = item.get("gender")
            country_id = item.get("country_id")

            if age is None or not gender or not country_id:
                skipped += 1
                continue

            normalized_name = name.lower()
            if normalized_name in existing_names:
                skipped += 1
                continue

            normalized_country_id = country_id.upper().strip()

            profile = Profile(
                name=name,
                gender=gender.lower().strip(),
                gender_probability=clamp_prob(item.get("gender_probability")),
                age=int(age),
                age_group=get_age_group(age),
                country_id=normalized_country_id,
                country_name=normalize_text(item.get("country_name"))
                or get_country_name_from_id(normalized_country_id),
                country_probability=clamp_prob(item.get("country_probability")),
                created_at=datetime.now(timezone.utc),
            )

            db.add(profile)
            existing_names.add(normalized_name)
            inserted += 1

        db.commit()
        print(f"Seed completed -> inserted: {inserted}, skipped: {skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_profiles()
