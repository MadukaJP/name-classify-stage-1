import re
from difflib import get_close_matches

import pycountry


GENDER_MAP = {
    "male": {"male", "males", "man", "men", "boy", "boys"},
    "female": {"female", "females", "woman", "women", "girl", "girls"},
}

AGE_GROUP_MAP = {
    "child": {"child", "children", "kid", "kids", "toddler", "toddlers"},
    "teenager": {"teen", "teens", "teenager", "teenagers", "teenage", "adolescent", "adolescents"},
    "adult": {"adult", "adults"},
    "senior": {"senior", "seniors", "elder", "elders", "elderly"},
}

AGE_RANGE_PHRASES = (
    (re.compile(r"\byoung[-\s]?adult(?:s)?\b"), (20, 35)),
    (re.compile(r"\byoung\b"), (16, 24)),
    (re.compile(r"\bmiddle[-\s]?aged\b"), (36, 55)),
    (re.compile(r"\bold\b"), (56, 80)),
    (re.compile(r"\belderly\b"), (81, 100)),
)

NAME_INTRO_RE = re.compile(r"\b(?:named|called|name is|names)\s+(.+)$", re.IGNORECASE)
NAME_SPLIT_RE = re.compile(r"\s*(?:and|&|,|/|\+)\s*", re.IGNORECASE)
NAME_TOKEN_RE = re.compile(r"^[a-z]+(?:[-'][a-z]+)?$", re.IGNORECASE)
EXPLICIT_NAME_MARKERS = ("named", "called", "name is", "names")
BARE_NAME_DENYLIST = {
    "all",
    "any",
    "data",
    "find",
    "get",
    "give",
    "hello",
    "list",
    "look",
    "people",
    "person",
    "profile",
    "profiles",
    "result",
    "results",
    "search",
    "show",
    "user",
    "users",
}
BARE_NAME_CONTEXT_WORDS = {
    "above",
    "between",
    "find",
    "from",
    "get",
    "give",
    "in",
    "list",
    "older",
    "over",
    "profile",
    "profiles",
    "search",
    "show",
    "under",
    "with",
    "without",
    "younger",
}
STOPWORDS = {
    "and",
    "from",
    "named",
    "called",
    "name",
    "is",
    "male",
    "males",
    "female",
    "females",
    "man",
    "men",
    "woman",
    "women",
    "boy",
    "boys",
    "girl",
    "girls",
    "teen",
    "teens",
    "teenager",
    "teenagers",
    "adult",
    "adults",
    "young",
    "senior",
    "seniors",
    "child",
    "children",
    "above",
    "under",
    "older",
    "younger",
    "between",
    "over",
    "than",
    "of",
    "in",
    "at",
    "to",
    "on",
    "for",
    "with",
    "the",
    "a",
    "an",
}

COUNTRY_ALIASES = {
    "usa": "US",
    "u.s.": "US",
    "united states": "US",
    "united states of america": "US",
    "uk": "GB",
}

COUNTRY_NAME_LOOKUP = {
    c.name.lower(): c.alpha_2 for c in pycountry.countries
}
for c in pycountry.countries:
    if hasattr(c, "official_name"):
        COUNTRY_NAME_LOOKUP[c.official_name.lower()] = c.alpha_2

COUNTRY_ALPHA_2_LOOKUP = {c.alpha_2.upper() for c in pycountry.countries}


def _dedupe_preserve_order(values):
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"\b" + re.escape(phrase).replace(r"\ ", r"[-\s]+") + r"\b"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _is_country_term(value: str) -> bool:
    if not value:
        return False

    normalized = value.strip().lower()
    if normalized in COUNTRY_ALIASES:
        return True

    if normalized in COUNTRY_NAME_LOOKUP:
        return True

    if normalized.upper() in COUNTRY_ALPHA_2_LOOKUP:
        return True

    return False


def _normalize_name_chunk(chunk: str):
    tokens = re.findall(r"[a-z]+(?:[-'][a-z]+)?", chunk.lower())
    if not tokens or len(tokens) > 3:
        return None

    if any(token in STOPWORDS for token in tokens):
        return None

    candidate = " ".join(tokens)
    if _is_country_term(candidate):
        return None

    if not all(NAME_TOKEN_RE.fullmatch(token) for token in tokens):
        return None

    return " ".join(token.capitalize() for token in tokens)


def _is_bare_name_like_query(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return False

    if re.search(r"[\n\r.!?;:]", normalized):
        return False

    lowered = normalized.lower()
    if any(marker in lowered for marker in EXPLICIT_NAME_MARKERS):
        return False

    tokens = re.findall(r"[a-z]+(?:[-'][a-z]+)?", lowered)
    if not tokens:
        return False

    if any(token in BARE_NAME_DENYLIST for token in tokens):
        return False

    if any(token in BARE_NAME_CONTEXT_WORDS for token in tokens):
        return False

    return True


def detect_gender_terms(text):
    tokens = re.findall(r"[a-z]+(?:[-'][a-z]+)?", text.lower())
    genders = []

    for token in tokens:
        for gender, words in GENDER_MAP.items():
            if token in words:
                genders.append(gender)

    return _dedupe_preserve_order(genders)


def detect_age_groups(text):
    text_lower = text.lower()
    age_groups = []

    for age_group, words in AGE_GROUP_MAP.items():
        if any(_contains_phrase(text_lower, word) for word in words):
            age_groups.append(age_group)

    return _dedupe_preserve_order(age_groups)


def detect_age_ranges(text):
    text_lower = text.lower()

    between = re.search(r"\bbetween\s*(\d+)\s*(?:and|-)\s*(\d+)\b", text_lower)
    above = re.search(r"\b(?:above|older than|over|at least|more than)\s*(\d+)\b", text_lower)
    under = re.search(r"\b(?:under|younger than|less than|below|up to)\s*(\d+)\b", text_lower)

    if between:
        return int(between.group(1)), int(between.group(2))
    if above:
        return int(above.group(1)), None
    if under:
        return None, int(under.group(1))

    for pattern, age_range in AGE_RANGE_PHRASES:
        if pattern.search(text_lower):
            return age_range

    exact = re.search(r"\b(\d{1,3})\b", text_lower)
    if exact:
        age = int(exact.group(1))
        return age, age

    return None, None


def detect_countries(text):
    found = []
    text_lower = text.lower()
    country_names = {c.name: c.alpha_2 for c in pycountry.countries}

    for c in pycountry.countries:
        if hasattr(c, "official_name"):
            country_names[c.official_name] = c.alpha_2

    for alias, code in COUNTRY_ALIASES.items():
        if _contains_phrase(text_lower, alias):
            found.append(code)

    for name, code in country_names.items():
        if _contains_phrase(text_lower, name.lower()):
            found.append(code)

    for word in re.findall(r"[a-z]+(?:[-'][a-z]+)?", text_lower):
        if len(word) < 4 or word in STOPWORDS:
            continue
        match = get_close_matches(word, country_names.keys(), n=1, cutoff=0.75)
        if match:
            found.append(country_names[match[0]])

    return _dedupe_preserve_order(found) if found else None


def detect_names(text):
    names = []

    intro_match = NAME_INTRO_RE.search(text)
    if intro_match:
        tail = intro_match.group(1)
        tail = re.split(
            r"\b(from|in|at|above|under|over|between|older than|younger than|"
            r"male|males|female|females|man|men|woman|women|boy|boys|girl|girls|"
            r"adult|adults|teen|teens|teenager|teenagers|senior|seniors|child|children|"
            r"young)\b",
            tail,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        for chunk in NAME_SPLIT_RE.split(tail):
            cleaned = chunk.strip(" ,.")
            if cleaned and re.fullmatch(r"[A-Z][A-Za-z'\-]*(?:\s+[A-Z][A-Za-z'\-]*)*", cleaned):
                names.append(cleaned)

    if names:
        return _dedupe_preserve_order(names)

    if not _is_bare_name_like_query(text):
        return None

    raw_chunks = [chunk.strip(" ,.") for chunk in NAME_SPLIT_RE.split(text) if chunk.strip(" ,.")]

    if len(raw_chunks) > 1:
        if len(raw_chunks) > 3:
            return None

        bare_names = []
        for chunk in raw_chunks:
            if len(re.findall(r"[a-z]+(?:[-'][a-z]+)?", chunk.lower())) != 1:
                return None

            normalized_name = _normalize_name_chunk(chunk)
            if not normalized_name:
                return None

            bare_names.append(normalized_name)

        return _dedupe_preserve_order(bare_names) if bare_names else None

    tokens = re.findall(r"[a-z]+(?:[-'][a-z]+)?", text.lower())
    if len(tokens) != 1:
        return None

    token = tokens[0]
    if len(token) < 2 or token in STOPWORDS or token in BARE_NAME_DENYLIST:
        return None

    if _is_country_term(token):
        return None

    return [token.capitalize()]


def detect_profile_filters(text):
    genders = detect_gender_terms(text)
    age_groups = detect_age_groups(text)
    min_age, max_age = detect_age_ranges(text)
    countries = detect_countries(text)
    names = detect_names(text)

    return {
        "age_range": (min_age, max_age),
        "age_group": age_groups or [],
        "genders": genders or [],
        "countries": countries or [],
        "names": names or [],
    }
