from fastapi import APIRouter
from .organization_invites import invites_router

organization_router = APIRouter(prefix="/organization", tags=["organization"])
organization_router.include_router(invites_router)
