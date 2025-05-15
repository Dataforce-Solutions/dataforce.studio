from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from dataforce_studio.models.base import Base


class TokenBlackListOrm(Base):
    __tablename__ = "token_black_list"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, nullable=False)
    expire_at: Mapped[int] = mapped_column(Integer, nullable=False)
