from pydantic import BaseModel, ConfigDict


class BaseOrmConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)
