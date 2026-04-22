from pydantic import BaseModel, ConfigDict, field_serializer
from datetime import datetime, timezone
from uuid import UUID

class ProfileOut(BaseModel):
    id: UUID
    name: str
    gender: str
    gender_probability: float
    age: int
    age_group: str
    country_id: str
    country_name: str
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

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)
