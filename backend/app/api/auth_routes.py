"""POST /auth/login — issue a JWT for valid credentials."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.schemas import LoginRequest, LoginResponse
from backend.app.auth import authenticate_user, create_access_token
from backend.app.database import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, req.email, req.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(sub=user.email, role=user.role)
    return LoginResponse(access_token=token, role=user.role, email=user.email)
