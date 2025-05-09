from pydantic import ConfigDict


class BaseOrmConfig:
    model_config = ConfigDict(from_attributes=True)
