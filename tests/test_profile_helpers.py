from starlette.datastructures import QueryParams

from routes.profile import build_pagination_links


class DummyURL:
    path = "/api/profiles/search"


class DummyRequest:
    url = DummyURL()
    query_params = QueryParams(
        "q=young+males+from+nigeria&gender=male&sort_by=age&order=desc&page=1&limit=10"
    )


def test_pagination_links_preserve_filters_sorting_and_path():
    links = build_pagination_links(DummyRequest(), page=1, limit=10, total_pages=3)

    assert links["prev"] is None
    assert links["self"] == (
        "/api/profiles/search?"
        "q=young+males+from+nigeria&gender=male&sort_by=age&order=desc&page=1&limit=10"
    )
    assert links["next"] == (
        "/api/profiles/search?"
        "q=young+males+from+nigeria&gender=male&sort_by=age&order=desc&page=2&limit=10"
    )
