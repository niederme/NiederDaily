import requests

NYT_URL = "https://api.nytimes.com/svc/topstories/v2/home.json"
PREFERRED_FORMATS = {"threeByTwoSmallAt2X", "mediumThreeByTwo210", "mediumThreeByTwo440"}


def _pick_thumbnail(multimedia: list) -> str | None:
    if not multimedia:
        return None
    for fmt in PREFERRED_FORMATS:
        for item in multimedia:
            if item.get("format") == fmt:
                return item.get("url")
    return multimedia[0].get("url") if multimedia else None


def nyt_block(api_key: str | None) -> list | None:
    if not api_key:
        return None
    try:
        resp = requests.get(NYT_URL, params={"api-key": api_key}, timeout=10)
        resp.raise_for_status()
        stories = resp.json().get("results", [])[:5]
        return [
            {
                "title": s.get("title", ""),
                "abstract": s.get("abstract", ""),
                "url": s.get("url", ""),
                "thumbnail": _pick_thumbnail(s.get("multimedia", [])),
            }
            for s in stories
        ]
    except Exception:
        return None
