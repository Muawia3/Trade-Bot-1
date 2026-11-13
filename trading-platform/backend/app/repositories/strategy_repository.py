"""
Repository for StrategyConfig operations.
"""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.strategy_config import StrategyConfig
from app.schemas.strategy import StrategyConfigCreate, StrategyConfigUpdate


class StrategyRepository:
    """Async repository for trading strategy configurations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_name(self, name: str) -> Optional[StrategyConfig]:
        """Fetch a strategy configuration by its unique name."""
        stmt = select(StrategyConfig).where(StrategyConfig.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, config_id: str) -> Optional[StrategyConfig]:
        """Fetch strategy configuration by ID."""
        stmt = select(StrategyConfig).where(StrategyConfig.id == config_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, enabled_only: bool = False) -> List[StrategyConfig]:
        """List all registered strategies."""
        stmt = select(StrategyConfig)
        if enabled_only:
            stmt = stmt.where(StrategyConfig.enabled == True)  # noqa: E712
        stmt = stmt.order_by(StrategyConfig.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_or_update(
        self, config_in: StrategyConfigCreate
    ) -> StrategyConfig:
        """Create a new strategy config or update if already existing by name."""
        existing = await self.get_by_name(config_in.name)
        if existing:
            existing.symbol = config_in.symbol
            existing.enabled = config_in.enabled
            existing.timeframe = config_in.timeframe
            existing.parameters = config_in.parameters
            existing.risk_percent = config_in.risk_percent
            existing.max_positions = config_in.max_positions
            await self.session.flush()
            await self.session.refresh(existing)
            return existing

        config = StrategyConfig(**config_in.model_dump())
        self.session.add(config)
        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def update(
        self, name: str, config_in: StrategyConfigUpdate
    ) -> Optional[StrategyConfig]:
        """Update fields on an existing strategy."""
        config = await self.get_by_name(name)
        if not config:
            return None

        update_data = config_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(config, key, value)

        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def toggle(self, name: str, enabled: bool) -> Optional[StrategyConfig]:
        """Toggle active execution status."""
        config = await self.get_by_name(name)
        if not config:
            return None
        config.enabled = enabled
        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def delete(self, name: str) -> bool:
        """Delete strategy configuration."""
        config = await self.get_by_name(name)
        if not config:
            return False
        await self.session.delete(config)
        await self.session.flush()
        return True
