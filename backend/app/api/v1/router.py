"""Aggregates every v1 route."""

from fastapi import APIRouter

from app.api.v1 import audit, auth, roles, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(roles.router)
api_router.include_router(audit.router)
