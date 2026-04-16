
from pydantic import BaseModel


class ProfileCreate(BaseModel):
    name: str
