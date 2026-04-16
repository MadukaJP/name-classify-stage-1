from typing import Literal

def custom_content(
    status: Literal["error", "success"],
    data: dict | None = None,
    message: str | None = None,
    count: int | None = None,
) -> dict:

    response = {"status": status}

    if message is not None:
        response["message"] = message

    if count is not None:
        response["count"] = count

    if data is not None:
        response["data"] = data

    return response