from pydantic import EmailStr

from dataforce_studio.schemas.organization import OrgRole


def generate_organization_name(email: EmailStr, full_name: str | None = None) -> str:
    if full_name:
        return f"{full_name.strip().split(' ')[0]}'s organization"
    return f"{str(email).split('@')[0]}'s organization"


def get_members_roles_count(members: list) -> dict:
    members_by_role = {
        str(OrgRole.OWNER): 0,
        str(OrgRole.ADMIN): 0,
        str(OrgRole.MEMBER): 0,
    }

    for member in members:
        if member.role in members_by_role:
            members_by_role[member.role] += 1

    return dict(members_by_role)
