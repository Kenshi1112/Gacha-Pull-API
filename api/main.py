from __future__ import annotations

import random
from typing import Literal

from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

RARITY_WEIGHTS: dict[str, int] = {"N": 60, "R": 27, "SR": 10, "SSR": 3}
RARITY_ORDER = ["N", "R", "SR", "SSR"]
PITY_THRESHOLD = 50
GUARANTEE_MIN_RARITY = "SR" 

USER_ID_PATTERN = r"^[a-zA-Z0-9_]{3,20}$"

RarityLiteral = Literal["N", "R", "SR", "SSR"]

ITEM_POOL: dict[str, list[dict[str, str]]] = {
    "N": [
        {"item_id": "itm_n_001", "name": "Rusty Nail"},
        {"item_id": "itm_n_002", "name": "Expired Bread"},
        {"item_id": "itm_n_003", "name": "Left Shoe"},
        {"item_id": "itm_n_004", "name": "Very Ordinary Stick"},
    ],
    "R": [
        {"item_id": "itm_r_001", "name": "Slightly Magical Stick"},
        {"item_id": "itm_r_002", "name": "Suspicious Soup"},
    ],
    "SR": [
        {"item_id": "itm_sr_001", "name": "Sword of Questionable Quality"},
        {"item_id": "itm_sr_002", "name": "Legendary Rice Cooker"},
    ],
    "SSR": [
        {"item_id": "itm_ssr_001", "name": "Mom's Slippers"},
        {"item_id": "itm_ssr_002", "name": "Excalibur (Plastic)"},
        {"item_id": "itm_ssr_003", "name": "Plot Armor"},
    ],
}

USER_STATE: dict[str, dict[str, int]] = {}


def get_or_create_user_state(user_id: str) -> dict[str, int]:
    if user_id not in USER_STATE:
        USER_STATE[user_id] = {"pity_count": 0, "total_pulls": 0}
    return USER_STATE[user_id]


def roll_rarity() -> str:
    rarities = list(RARITY_WEIGHTS.keys())
    weights = list(RARITY_WEIGHTS.values())
    return random.choices(rarities, weights=weights, k=1)[0]


def draw_item(rarity: str) -> dict[str, str]:
    return random.choice(ITEM_POOL[rarity])


def is_at_least(rarity: str, minimum: str) -> bool:
    return RARITY_ORDER.index(rarity) >= RARITY_ORDER.index(minimum)


def pull_one(state: dict[str, int]) -> tuple[dict[str, str], bool]:

    pity_triggered = state["pity_count"] >= PITY_THRESHOLD
    rarity = "SSR" if pity_triggered else roll_rarity()

    if rarity == "SSR":
        state["pity_count"] = 0
    else:
        state["pity_count"] += 1

    state["total_pulls"] += 1
    item = draw_item(rarity)
    return {**item, "rarity": rarity}, pity_triggered

class PullRequest(BaseModel):
    user_id: str = Field(..., pattern=USER_ID_PATTERN)

class Item(BaseModel):
    item_id: str
    name: str
    rarity: RarityLiteral

class PullResponse(BaseModel):
    user_id: str
    item: Item
    pity_count: int
    pity_triggered: bool

class PullX10Response(BaseModel):
    user_id: str
    items: list[Item]
    guarantee_triggered: bool
    pity_count: int

class RateEntry(BaseModel):
    rarity: RarityLiteral
    percentage: float

class RatesResponse(BaseModel):
    rates: list[RateEntry]
    pity_threshold: int
    pull_x10_guarantee_min_rarity: RarityLiteral

class PityResponse(BaseModel):
    user_id: str
    current_pity_count: int
    pity_threshold: int
    pulls_until_pity: int
    total_pulls: int


app = FastAPI(
    title="Gacha Pull API",
    version="1.0.0",
    description="Mock gacha pull system — QA/testing portfolio project.",
)


def _is_unparseable_body_error(err: dict) -> bool:
    if err.get("type") == "json_invalid":
        return True
    if err.get("type") == "model_attributes_type" and isinstance(err.get("input"), (bytes, bytearray)):
        return True
    return False


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if any(_is_unparseable_body_error(e) for e in errors):
        return JSONResponse(status_code=400, content={"detail": "Invalid request body"})
    safe_errors = jsonable_encoder(errors, custom_encoder={bytes: lambda b: b.decode("utf-8", "replace")})
    return JSONResponse(status_code=422, content={"detail": safe_errors})


@app.post("/pull", response_model=PullResponse, tags=["Pull"])
def pull(body: PullRequest) -> PullResponse:
    state = get_or_create_user_state(body.user_id)
    item, pity_triggered = pull_one(state)
    return PullResponse(
        user_id=body.user_id,
        item=Item(**item),
        pity_count=state["pity_count"],
        pity_triggered=pity_triggered,
    )


@app.post("/pull-x10", response_model=PullX10Response, tags=["Pull"])
def pull_x10(body: PullRequest) -> PullX10Response:
    state = get_or_create_user_state(body.user_id)
    items: list[dict[str, str]] = []
    guarantee_triggered = False

    for i in range(10):
        is_last = i == 9
        already_has_guarantee = any(
            is_at_least(it["rarity"], GUARANTEE_MIN_RARITY) for it in items
        )

        if is_last and not already_has_guarantee and state["pity_count"] < PITY_THRESHOLD:
            rarity = GUARANTEE_MIN_RARITY
            state["pity_count"] += 1
            state["total_pulls"] += 1
            item = {**draw_item(rarity), "rarity": rarity}
            guarantee_triggered = True
        else:
            item, _pity_triggered = pull_one(state)

        items.append(item)

    return PullX10Response(
        user_id=body.user_id,
        items=[Item(**it) for it in items],
        guarantee_triggered=guarantee_triggered,
        pity_count=state["pity_count"],
    )

@app.get("/rates", response_model=RatesResponse, tags=["Rates"])
def get_rates() -> RatesResponse:
    assert sum(RARITY_WEIGHTS.values()) == 100
    return RatesResponse(
        rates=[
            RateEntry(rarity=r, percentage=RARITY_WEIGHTS[r])
            for r in ["SSR", "SR", "R", "N"]
        ],
        pity_threshold=PITY_THRESHOLD,
        pull_x10_guarantee_min_rarity=GUARANTEE_MIN_RARITY,
    )

@app.get("/pity/{user_id}", response_model=PityResponse, tags=["Pity"])
def get_pity(
    user_id: str = Path(..., pattern=USER_ID_PATTERN),
) -> PityResponse:
    state = USER_STATE.get(user_id, {"pity_count": 0, "total_pulls": 0})
    return PityResponse(
        user_id=user_id,
        current_pity_count=state["pity_count"],
        pity_threshold=PITY_THRESHOLD,
        pulls_until_pity=PITY_THRESHOLD - state["pity_count"],
        total_pulls=state["total_pulls"],
    )