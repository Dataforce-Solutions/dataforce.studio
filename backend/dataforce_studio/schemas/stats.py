from datetime import datetime

from pydantic import BaseModel, EmailStr

from dataforce_studio.schemas.base import BaseOrmConfig


class StatsEmailSendCreate(BaseModel):
    email: EmailStr
    description: str


class StatsEmailSendOut(BaseModel, BaseOrmConfig):
    id: int
    email: EmailStr
    description: str
    created_at: datetime
