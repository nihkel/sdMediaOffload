from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from ..services import auth as auth_svc


router = APIRouter()


class LoginIn(BaseModel):
    password: str


@router.get("/status")
def status(request: Request):
    required = auth_svc.auth_required()
    token = request.cookies.get(auth_svc.COOKIE_NAME, "")
    return {"required": required, "authenticated": (not required) or auth_svc.verify_token(token)}


@router.post("/login")
def login(payload: LoginIn, response: Response):
    if not auth_svc.auth_required():
        return {"ok": True, "auth_required": False}
    if not auth_svc.check_password(payload.password):
        raise HTTPException(401, "invalid password")
    token = auth_svc.issue_token()
    response.set_cookie(
        key=auth_svc.COOKIE_NAME,
        value=token,
        max_age=auth_svc.SESSION_TTL,
        httponly=True,
        samesite="lax",
        secure=False,  # serving over plain HTTP on LAN; flip when behind TLS
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth_svc.COOKIE_NAME)
    return {"ok": True}
