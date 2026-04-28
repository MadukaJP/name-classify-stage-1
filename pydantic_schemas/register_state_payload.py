from pydantic import BaseModel

class RegisterStatePayload(BaseModel):
    state:         str
    code_verifier: str   
    mode:          str = "cli"