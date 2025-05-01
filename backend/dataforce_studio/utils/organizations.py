def generate_organization_name(email: str, full_name: str | None = None) -> str:
    if full_name:
        return f"{full_name.strip().split(" ")[0]}'s organization"
    return f"{email.split("@")[0]}'s organization"
