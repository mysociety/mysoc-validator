"""Models for non-standard Popolo ``extra`` fields."""

from pydantic import BaseModel, ConfigDict


class Extra(BaseModel):
    """Forward-compatible container for non-specification Popolo properties."""

    model_config = ConfigDict(extra="allow")
