from pydantic import EmailStr
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from dataforce_studio.models.base import Base, TimestampMixin
from dataforce_studio.schemas.stats import StatsEmailSendOut


class StatsEmailSendOrm(TimestampMixin, Base):
    __tablename__ = "stats_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[EmailStr] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return (
            f"StatsEmailSend(id={self.id!r}, email={self.email!r}, "
            f"description={self.description!r})"
        )

    def to_email_send(self) -> StatsEmailSendOut:
        return StatsEmailSendOut.model_validate(self)
