from pydantic import BaseModel, ConfigDict, field_serializer
from datetime import datetime, timezone

class ProfileOut(BaseModel):
    id: str
    name: str
    gender: str
    gender_probability: float
    sample_size: int
    age: int
    age_group: str
    country_id: str
    country_probability: float
    created_at: datetime  # keep as ISO string for API

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        # Always normalize to UTC and use Z suffix (ISO 8601 standard)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)

        return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")
