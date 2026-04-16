from pydantic import BaseModel, ConfigDict

class ProfilesOut(BaseModel):
    id: str
    name: str
    gender: str
    age: int
    age_group: str
    country_id: str

    model_config = ConfigDict(from_attributes=True)

