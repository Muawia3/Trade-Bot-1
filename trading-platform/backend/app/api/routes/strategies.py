"""
Strategy configuration and runtime management endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.repositories.strategy_repository import StrategyRepository
from app.schemas.strategy import (
    StrategyConfigCreate,
    StrategyConfigResponse,
    StrategyConfigUpdate,
    StrategyToggle,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=List[StrategyConfigResponse])
async def list_strategies(
    enabled_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> List[StrategyConfigResponse]:
    """List all registered trading strategies and their parameters."""
    repo = StrategyRepository(db)
    strategies = await repo.get_all(enabled_only=enabled_only)
    return [StrategyConfigResponse.model_validate(s) for s in strategies]


@router.get("/{name}", response_model=StrategyConfigResponse)
async def get_strategy(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> StrategyConfigResponse:
    """Get single strategy configuration by unique name."""
    repo = StrategyRepository(db)
    strategy = await repo.get_by_name(name)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy '{name}' not found.",
        )
    return StrategyConfigResponse.model_validate(strategy)


@router.post("", response_model=StrategyConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_strategy(
    strategy_in: StrategyConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> StrategyConfigResponse:
    """Create or update strategy configuration and risk limits."""
    repo = StrategyRepository(db)
    strategy = await repo.create_or_update(strategy_in)
    return StrategyConfigResponse.model_validate(strategy)


@router.patch("/{name}", response_model=StrategyConfigResponse)
async def update_strategy(
    name: str,
    strategy_in: StrategyConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> StrategyConfigResponse:
    """Update hyper-parameters or limits for a strategy."""
    repo = StrategyRepository(db)
    strategy = await repo.update(name, strategy_in)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy '{name}' not found.",
        )
    return StrategyConfigResponse.model_validate(strategy)


@router.post("/{name}/toggle", response_model=StrategyConfigResponse)
async def toggle_strategy(
    name: str,
    toggle_in: StrategyToggle,
    db: AsyncSession = Depends(get_db),
) -> StrategyConfigResponse:
    """Enable or disable strategy execution."""
    repo = StrategyRepository(db)
    strategy = await repo.toggle(name, toggle_in.enabled)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy '{name}' not found.",
        )
    return StrategyConfigResponse.model_validate(strategy)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a strategy configuration."""
    repo = StrategyRepository(db)
    success = await repo.delete(name)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy '{name}' not found.",
        )
