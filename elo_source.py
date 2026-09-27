from __future__ import annotations

import json
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


# =========================================================
# CONFIG
# =========================================================

CLAX_ELO_URL = "https://dcdl-laxou.fr/ts/elo/#/global"

BASE_DIR = Path(__file__).resolve().parent

DEFAULT_OVERRIDES_FILE = BASE_DIR / "data" / "overrides.json"

CLAX_CACHE_FILE = BASE_DIR / "data" / "clax_cache.json"

CLAX_CACHE_TTL_MINUTES = 60


# =========================================================
# NORMALISATION
# =========================================================

def normalize_name(name: Any) -> str:
    return " ".join(
        str(name)
        .strip()
        .split()
    )


def normalize_key(name: Any) -> str:
    return normalize_name(
        name
    ).casefold()


def normalize_field_name(name: Any) -> str:
    text = (
        str(name)
        .strip()
        .casefold()
    )

    text = unicodedata.normalize(
        "NFD",
        text
    )

    text = "".join(
        c
        for c in text
        if unicodedata.category(c)
        != "Mn"
    )

    return (
        text
        .replace("_", " ")
        .replace("-", " ")
    )


def parse_number(value: Any):
    if value is None:
        return None

    if isinstance(
        value,
        (int, float)
    ):
        return float(value)

    text = str(
        value
    ).strip()

    if (
        not text
        or text.casefold()
        in {
            "nan",
            "none",
            "null",
        }
    ):
        return None

    text = (
        text
        .replace("\u202f", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .replace(",", ".")
    )

    try:
        return float(
            text
        )

    except (
        ValueError,
        TypeError,
    ):
        return None


# =========================================================
# CACHE CLAX
# =========================================================

def load_clax_cache():
    if not CLAX_CACHE_FILE.exists():
        return None

    try:
        with CLAX_CACHE_FILE.open(
            "r",
            encoding="utf-8"
        ) as f:
            cache = json.load(f)

        updated_at = datetime.fromisoformat(
            cache["updated_at"]
        )

        age = (
            datetime.now()
            - updated_at
        )

        if age > timedelta(
            minutes=CLAX_CACHE_TTL_MINUTES
        ):
            return None

        players = cache.get(
            "players",
            []
        )

        if len(players) < 20:
            return None

        return players

    except Exception:
        return None


def save_clax_cache(players):
    CLAX_CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with CLAX_CACHE_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            {
                "updated_at": (
                    datetime.now()
                    .isoformat()
                ),
                "players": players,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def clear_clax_cache():
    if CLAX_CACHE_FILE.exists():
        CLAX_CACHE_FILE.unlink()


# =========================================================
# SELENIUM
# =========================================================

def build_driver():
    options = Options()

    options.add_argument(
        "--headless=new"
    )

    options.add_argument(
        "--no-sandbox"
    )

    options.add_argument(
        "--disable-dev-shm-usage"
    )

    options.add_argument(
        "--disable-gpu"
    )

    options.add_argument(
        "--window-size=1920,1080"
    )

    options.set_capability(
        "goog:loggingPrefs",
        {
            "performance": "ALL"
        }
    )

    return webdriver.Chrome(
        options=options
    )


# =========================================================
# INTERCEPTION RESEAU
# =========================================================

def get_json_network_responses(
    driver
):
    responses = []

    logs = driver.get_log(
        "performance"
    )

    for item in logs:

        try:
            message = json.loads(
                item["message"]
            )["message"]

        except Exception:
            continue

        if (
            message.get("method")
            != "Network.responseReceived"
        ):
            continue

        params = message.get(
            "params",
            {}
        )

        response = params.get(
            "response",
            {}
        )

        resource_type = params.get(
            "type",
            ""
        )

        mime_type = response.get(
            "mimeType",
            ""
        )

        url = response.get(
            "url",
            ""
        )

        if (
            resource_type
            not in {
                "XHR",
                "Fetch",
            }
            and
            "json"
            not in mime_type.casefold()
        ):
            continue

        request_id = params.get(
            "requestId"
        )

        if not request_id:
            continue

        try:
            body_data = (
                driver
                .execute_cdp_cmd(
                    "Network.getResponseBody",
                    {
                        "requestId":
                            request_id
                    }
                )
            )

            body = body_data.get(
                "body",
                ""
            )

            if not body:
                continue

            data = json.loads(
                body
            )

            responses.append(
                {
                    "url": url,
                    "mime_type":
                        mime_type,
                    "data": data,
                }
            )

        except Exception:
            continue

    return responses


# =========================================================
# RECONNAISSANCE JSON
# =========================================================

PLAYER_FIELDS = {
    "player",
    "joueur",
    "name",
    "fullname",
    "full name",
    "nom complet",
    "nomcomplet",
}

LASTNAME_FIELDS = {
    "nom",
    "lastname",
    "last name",
}

FIRSTNAME_FIELDS = {
    "prenom",
    "firstname",
    "first name",
}

ELO_FIELDS = {
    "elo",
    "elo points",
    "points elo",
    "rating",
    "elo rating",
}

POINT_FIELDS = {
    "points",
}


def get_value_by_fields(
    item: dict,
    wanted_fields: set[str]
):
    normalized = {
        normalize_field_name(
            key
        ): value
        for key, value
        in item.items()
    }

    for field in wanted_fields:

        key = normalize_field_name(
            field
        )

        if key in normalized:
            return normalized[
                key
            ]

    return None


def extract_player_name(
    item: dict
):
    direct = get_value_by_fields(
        item,
        PLAYER_FIELDS
    )

    if direct is not None:

        name = normalize_name(
            direct
        )

        if (
            name
            and name.casefold()
            not in {
                "nan",
                "none",
                "null",
            }
        ):
            return name

    last_name = get_value_by_fields(
        item,
        LASTNAME_FIELDS
    )

    first_name = get_value_by_fields(
        item,
        FIRSTNAME_FIELDS
    )

    if (
        last_name is not None
        or first_name is not None
    ):

        parts = []

        if last_name is not None:
            parts.append(
                normalize_name(
                    last_name
                )
            )

        if first_name is not None:
            parts.append(
                normalize_name(
                    first_name
                )
            )

        name = normalize_name(
            " ".join(parts)
        )

        if name:
            return name

    return None


def extract_elo(
    item: dict
):
    value = get_value_by_fields(
        item,
        ELO_FIELDS
    )

    number = parse_number(
        value
    )

    if (
        number is not None
        and 500 <= number <= 3000
    ):
        return (
            int(round(number)),
            100,
        )

    value = get_value_by_fields(
        item,
        POINT_FIELDS
    )

    number = parse_number(
        value
    )

    if (
        number is not None
        and 500 <= number <= 3000
    ):
        return (
            int(round(number)),
            20,
        )

    return (
        None,
        0,
    )


def extract_optional_int(
    item: dict,
    keywords
):
    for key, value in item.items():

        normalized_key = (
            normalize_field_name(
                key
            )
        )

        if any(
            keyword
            in normalized_key
            for keyword
            in keywords
        ):

            number = parse_number(
                value
            )

            if number is not None:
                return int(
                    round(number)
                )

    return 0


def list_to_players(
    items
):
    if (
        not isinstance(
            items,
            list
        )
        or len(items) < 10
    ):
        return None

    players = []

    explicit_elo_score = 0

    for item in items:

        if not isinstance(
            item,
            dict
        ):
            continue

        name = extract_player_name(
            item
        )

        elo, elo_score = (
            extract_elo(
                item
            )
        )

        if (
            not name
            or elo is None
        ):
            continue

        explicit_elo_score += (
            elo_score
        )

        players.append(
            {
                "player": name,
                "points": elo,
                "games":
                    extract_optional_int(
                        item,
                        (
                            "match",
                            "partie",
                            "game",
                            "joue",
                        )
                    ),
                "inactivity":
                    extract_optional_int(
                        item,
                        (
                            "inactiv",
                        )
                    ),
                "history": [],
                "source": "CLAX",
            }
        )

    min_valid = max(
        10,
        int(
            len(items)
            * 0.50
        )
    )

    if len(players) < min_valid:
        return None

    unique = {}

    for player in players:

        unique[
            normalize_key(
                player["player"]
            )
        ] = player

    players = list(
        unique.values()
    )

    if len(players) < 10:
        return None

    score = (
        len(players)
        * 10
        + explicit_elo_score
    )

    return (
        score,
        players,
    )


def find_player_lists(
    obj
):
    candidates = []

    if isinstance(
        obj,
        list
    ):

        candidate = list_to_players(
            obj
        )

        if candidate is not None:
            candidates.append(
                candidate
            )

        for value in obj:

            candidates.extend(
                find_player_lists(
                    value
                )
            )

    elif isinstance(
        obj,
        dict
    ):

        for value in obj.values():

            candidates.extend(
                find_player_lists(
                    value
                )
            )

    return candidates


# =========================================================
# RÉCUPÉRATION CLAX WEB
# =========================================================

def fetch_clax_players_from_web():
    driver = build_driver()

    try:

        driver.execute_cdp_cmd(
            "Network.enable",
            {}
        )

        driver.get(
            CLAX_ELO_URL
        )

        # On laisse la SPA charger ses requêtes réseau.
        time.sleep(
            6
        )

        responses = (
            get_json_network_responses(
                driver
            )
        )

    finally:
        driver.quit()

    if not responses:

        raise RuntimeError(
            "CLAX a été chargé mais aucune "
            "réponse JSON/XHR n'a pu être interceptée."
        )

    candidates = []

    for response in responses:

        response_candidates = (
            find_player_lists(
                response[
                    "data"
                ]
            )
        )

        for (
            score,
            players,
        ) in response_candidates:

            candidates.append(
                {
                    "score":
                        score,
                    "players":
                        players,
                    "url":
                        response[
                            "url"
                        ],
                }
            )

    if not candidates:

        urls = [
            response[
                "url"
            ]
            for response
            in responses
        ]

        raise RuntimeError(
            "Des réponses JSON CLAX ont été "
            "interceptées, mais aucun classement "
            "Elo n'a été reconnu.\n\n"
            "Endpoints interceptés :\n- "
            + "\n- ".join(
                urls
            )
        )

    best = max(
        candidates,
        key=lambda candidate:
            candidate[
                "score"
            ]
    )

    players = best[
        "players"
    ]

    if len(players) < 20:

        raise RuntimeError(
            f"Seulement "
            f"{len(players)} joueurs "
            f"ont été détectés dans "
            f"{best['url']}"
        )

    players.sort(
        key=lambda p: (
            -int(
                p["points"]
            ),
            normalize_key(
                p["player"]
            ),
        )
    )

    return players


# =========================================================
# RÉCUPÉRATION AVEC CACHE
# =========================================================

def fetch_clax_players(
    force_refresh=False
):
    if not force_refresh:

        cached_players = (
            load_clax_cache()
        )

        if cached_players is not None:
            return cached_players

    players = (
        fetch_clax_players_from_web()
    )

    save_clax_cache(
        players
    )

    return players


# =========================================================
# OVERRIDES
# =========================================================

def load_overrides(
    filepath=DEFAULT_OVERRIDES_FILE
):
    path = Path(
        filepath
    )

    if not path.exists():
        return {
            "global": {},
            "players": {},
        }

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(
            f
        )

    if not isinstance(
        data,
        dict
    ):
        raise ValueError(
            "overrides.json doit contenir "
            "un objet JSON."
        )

    data.setdefault(
        "global",
        {}
    )

    data.setdefault(
        "players",
        {}
    )

    return data


# =========================================================
# SOURCE UNIQUE JOUEURS
# =========================================================

def get_players(
    overrides_file=DEFAULT_OVERRIDES_FILE,
    apply_manual_elo=True,
):
    clax_players = (
        fetch_clax_players()
    )

    players = {
        normalize_key(
            player[
                "player"
            ]
        ): dict(
            player
        )
        for player
        in clax_players
    }

    overrides = load_overrides(
        overrides_file
    )

    for (
        player_name,
        config,
    ) in overrides.get(
        "players",
        {}
    ).items():

        if not isinstance(
            config,
            dict
        ):
            continue

        clean_name = normalize_name(
            player_name
        )

        if not clean_name:
            continue

        manual_elo = config.get(
            "manual_elo"
        )

        if manual_elo is None:
            continue

        key = normalize_key(
            clean_name
        )

        if key in players:

            if apply_manual_elo:

                players[
                    key
                ][
                    "points"
                ] = int(
                    manual_elo
                )

                players[
                    key
                ][
                    "source"
                ] = (
                    "manual_override"
                )

        else:

            players[
                key
            ] = {
                "player":
                    clean_name,
                "points":
                    int(
                        manual_elo
                    ),
                "games":
                    0,
                "inactivity":
                    0,
                "history":
                    [],
                "source":
                    "manual",
            }

    result = list(
        players.values()
    )

    result.sort(
        key=lambda p: (
            -int(
                p[
                    "points"
                ]
            ),
            normalize_key(
                p[
                    "player"
                ]
            ),
        )
    )

    return result


# =========================================================
# DATAFRAME POUR STREAMLIT
# =========================================================

def get_players_dataframe(
    overrides_file=DEFAULT_OVERRIDES_FILE,
    apply_manual_elo=True,
):
    players = get_players(
        overrides_file=
            overrides_file,
        apply_manual_elo=
            apply_manual_elo,
    )

    return pd.DataFrame(
        [
            {
                "player":
                    p[
                        "player"
                    ],
                "points":
                    p[
                        "points"
                    ],
                "games":
                    p.get(
                        "games",
                        0,
                    ),
                "inactivity":
                    p.get(
                        "inactivity",
                        0,
                    ),
                "source":
                    p.get(
                        "source",
                        "CLAX",
                    ),
            }
            for p
            in players
        ]
    )