import asyncio

from fastapi import Request
from fastapi.responses import JSONResponse

from utils import custom_content

# Single fetch
async def single_external_data(client, api_name, url):
    try:
        res = await client.get(url)
        if res.status_code != 200:
            return {
                "error": True,
                "message": f"{api_name} returned an invalid response",
            }
        return {"error": False, "api": api_name, "data": res.json()}
    except Exception:
        return {"error": True, "message": f"{api_name} request an invalid response"}


# fetch all external data
async def all_external_data(request: Request, name: str):

    client = request.app.state.client

    tasks = [
        single_external_data(
            client, "Genderize", f"https://api.genderize.io?name={name}"
        ),
        single_external_data(client, "Agify", f"https://api.agify.io/?name={name}"),
        single_external_data(
            client, "Nationalize", f"https://api.nationalize.io/?name={name}"
        ),
    ]

    pending = [asyncio.create_task(t) for t in tasks]

    try:
        for task in asyncio.as_completed(pending):
            result = await task

            # Fail immediately on first error (real-time)
            if result["error"]:
                # Cancel remaining requests
                for p in pending:
                    if not p.done():
                        p.cancel()

                return JSONResponse(
                    status_code=502,
                    content=custom_content("error", message=result["message"]),
                )

        # If all succeed
        results = [await t for t in pending]

        return {r["api"].lower(): r["data"] for r in results}

    except asyncio.CancelledError:
        pass

