"""Shared schema primitives."""

from pydantic import BaseModel, ConfigDict


class SchemaBase(BaseModel):
    """Base schema with common defaults."""

    model_config = ConfigDict(from_attributes=True)
