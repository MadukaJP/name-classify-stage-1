from typing import Literal, Optional

def custom_content(
    status: Literal["error", "success"],
    data: Optional[dict] = None,
    message: Optional[str] = None,
    count: Optional[int] = None,
    page: Optional[int] = None,
    limit: Optional[int] = None,
    total: Optional[int] = None,
) -> dict:
    response = {"status": status}

    if message is not None:
        response["message"] = message

    if count is not None:
        response["count"] = count

    if page is not None:
        response["page"] = page

    if limit is not None:
        response["limit"] = limit

    if total is not None:
        response["total"] = total

    if data is not None:
        response["data"] = data

    return response