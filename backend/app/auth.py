from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

USERNAME = "user"
PASSWORD = "password"

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get("/session")
def get_session(request: Request) -> dict[str, bool]:
    return {"authenticated": bool(request.session.get("authenticated"))}


@router.post("/login")
def login(payload: LoginRequest, request: Request) -> dict[str, bool]:
    if payload.username != USERNAME or payload.password != PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    request.session["authenticated"] = True
    return {"authenticated": True}


@router.post("/logout")
def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"authenticated": False}


def require_auth(request: Request) -> None:
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")


@router.get("/me")
def me(request: Request, _: None = Depends(require_auth)) -> dict[str, str]:
    return {"username": USERNAME}
