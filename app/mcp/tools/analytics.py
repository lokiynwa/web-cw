"""Read-only MCP tools for analytics queries."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.services.affordability_service import city_affordability_score, city_area_affordability
from app.services.cost_analytics_service import city_cost_analytics
from app.services.rent_analytics_service import area_rent_analytics, city_rent_analytics

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


@contextmanager
def _db_session() -> Iterator[Session]:
    """Open and close a database session for MCP tool execution."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _raise_tool_error_from_http_exception(exc: HTTPException) -> None:
    """Convert FastAPI-style HTTP errors into MCP tool errors."""
    detail = exc.detail
    if isinstance(detail, dict):
        message = f"[{exc.status_code}] {detail.get('message', detail)}"
    else:
        message = f"[{exc.status_code}] {detail}"
    raise ValueError(message) from exc


def register_analytics_tools(server: FastMCP) -> None:
    """Register read-only analytics tools on the MCP server."""

    @server.tool()
    def get_city_rent_analytics(
        city: str,
        bedrooms: int | None = None,
        property_type: str | None = None,
        ensuite_proxy: bool | None = None,
    ) -> dict:
        """Get city-level rent metrics using valid cleaned listings."""
        with _db_session() as db:
            try:
                return city_rent_analytics(
                    db,
                    city=city,
                    bedrooms=bedrooms,
                    property_type=property_type,
                    ensuite_proxy=ensuite_proxy,
                )
            except HTTPException as exc:
                _raise_tool_error_from_http_exception(exc)

    @server.tool()
    def get_area_rent_analytics(
        city: str,
        area: str,
        bedrooms: int | None = None,
        property_type: str | None = None,
        ensuite_proxy: bool | None = None,
    ) -> dict:
        """Get area-level rent metrics for a city."""
        with _db_session() as db:
            try:
                return area_rent_analytics(
                    db,
                    city=city,
                    area=area,
                    bedrooms=bedrooms,
                    property_type=property_type,
                    ensuite_proxy=ensuite_proxy,
                )
            except HTTPException as exc:
                _raise_tool_error_from_http_exception(exc)

    @server.tool()
    def list_city_areas_by_affordability(
        city: str,
        components: str | None = None,
        rent_weight: float | None = None,
        pint_weight: float | None = None,
        takeaway_weight: float | None = None,
    ) -> dict:
        """List per-area affordability scores and component breakdowns for a city."""
        with _db_session() as db:
            try:
                return city_area_affordability(
                    db,
                    city=city,
                    components=components,
                    rent_weight=rent_weight,
                    pint_weight=pint_weight,
                    takeaway_weight=takeaway_weight,
                )
            except HTTPException as exc:
                _raise_tool_error_from_http_exception(exc)

    @server.tool()
    def get_city_cost_analytics(
        city: str,
        submission_type: str | None = None,
    ) -> dict:
        """Get approved crowd-cost metrics for a city, optionally filtered by submission type."""
        with _db_session() as db:
            try:
                return city_cost_analytics(
                    db,
                    city=city,
                    submission_type=submission_type,
                )
            except HTTPException as exc:
                _raise_tool_error_from_http_exception(exc)

    @server.tool()
    def get_affordability_score(
        city: str,
        components: str | None = None,
        rent_weight: float | None = None,
        pint_weight: float | None = None,
        takeaway_weight: float | None = None,
    ) -> dict:
        """Get bounded city affordability score with transparent component contributions."""
        with _db_session() as db:
            try:
                return city_affordability_score(
                    db,
                    city=city,
                    components=components,
                    rent_weight=rent_weight,
                    pint_weight=pint_weight,
                    takeaway_weight=takeaway_weight,
                )
            except HTTPException as exc:
                _raise_tool_error_from_http_exception(exc)
