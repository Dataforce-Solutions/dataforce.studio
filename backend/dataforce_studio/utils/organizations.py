from pydantic import EmailStr


def generate_organization_name(email: EmailStr, full_name: str | None = None) -> str:
    if full_name:
        return f"{full_name.strip().split(' ')[0]}'s organization"
    return f"{str(email).split('@')[0]}'s organization"
