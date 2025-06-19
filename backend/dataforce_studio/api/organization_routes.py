from fastapi import APIRouter, Depends

from dataforce_studio.api.orbits.orbit_collections import collections_router
from dataforce_studio.api.orbits.orbit_ml_models import ml_models_router
from dataforce_studio.api.orbits.orbits import organization_orbits_router
from dataforce_studio.api.orbits.orbits_members import orbit_members_router
from dataforce_studio.api.organization.organization_bucket_secrets import (
    bucket_secrets_router,
)
from dataforce_studio.api.organization.organization_invites import invites_router
from dataforce_studio.api.organization.organization_members import members_router
from dataforce_studio.infra.dependencies import is_user_authenticated

organization_all_routers = APIRouter(
    prefix="/organizations",
    dependencies=[Depends(is_user_authenticated)],
)

organization_all_routers.include_router(invites_router)
organization_all_routers.include_router(members_router)
organization_all_routers.include_router(organization_orbits_router)
organization_all_routers.include_router(orbit_members_router)
organization_all_routers.include_router(bucket_secrets_router)
organization_all_routers.include_router(collections_router)
organization_all_routers.include_router(ml_models_router)
