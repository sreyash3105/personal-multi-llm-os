# backend/modules/router/api_router.py
from fastapi import APIRouter, Body
from pydantic import BaseModel
from typing import Optional

from backend.modules.router.router import classify_intent, route_request

router = APIRouter(prefix="/api/router", tags=["router"])

class ClassifyIn(BaseModel):
    text: str
    source: Optional[str] = "chat"

class RouteIn(BaseModel):
    text: str
    profile_id: Optional[str] = None
    chat_id: Optional[str] = None
    source: Optional[str] = "chat"
    execute: Optional[bool] = False

@router.post("/classify")
def api_classify(body: ClassifyIn):
    return classify_intent(body.text)

@router.post("/route")
def api_route(body: RouteIn):
    return route_request(body.dict())
