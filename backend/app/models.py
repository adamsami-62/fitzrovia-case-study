from datetime import datetime
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    address: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    scraper_key: Mapped[str] = mapped_column(String(64), unique=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_scrape_status: Mapped[str] = mapped_column(String(32), default="never")
    last_scrape_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    current_incentive_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_incentive_parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    incentive_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    incentive_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    incentive_source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    units: Mapped[list["Unit"]] = relationship(back_populates="building", cascade="all, delete-orphan")


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), index=True)
    unit_identifier: Mapped[str] = mapped_column(String(128))
    unit_type: Mapped[str] = mapped_column(String(32), index=True)
    rent: Mapped[float] = mapped_column(Float)
    sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incentive_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    incentive_parsed: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    floor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    available_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    listing_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    listing_type: Mapped[str] = mapped_column(String(32), default="specific_unit")
    is_currently_available: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    building: Mapped[Building] = relationship(back_populates="units")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    buildings_attempted: Mapped[int] = mapped_column(Integer, default=0)
    buildings_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    total_units_found: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScrapeSnapshot(Base):
    __tablename__ = "scrape_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("scrape_runs.id"), index=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), index=True)
    unit_identifier: Mapped[str] = mapped_column(String(128))
    unit_type: Mapped[str] = mapped_column(String(32))
    rent: Mapped[float] = mapped_column(Float)
    sqft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    incentive_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
