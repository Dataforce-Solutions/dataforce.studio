from fastapi import APIRouter
from .organization_invites import invites_router
from .organization_members import members_router

organization_router = APIRouter(prefix="/organization")
organization_router.include_router(invites_router)
organization_router.include_router(members_router)
