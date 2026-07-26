"""Core data model.

Mirrors the entities defined in the coding brief (Source, CollectionRun,
RawDocument, Property, Opportunity, SourceListing, Contact, RiskFlag, Score,
DueDiligenceItem, AuditLog). User accounts, Watchlist and the web API are
intentionally deferred - this edition of the app is a scheduled pipeline that
emails a report, not a multi-user dashboard. The schema below is written so a
future dashboard phase can be bolted on without a rewrite.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Controlled vocabularies (plain strings + application-level validation via
# Pydantic schemas, rather than DB enums, to keep SQLite migrations painless)
# ---------------------------------------------------------------------------

SOURCE_TYPES = (
    "government_gazette", "provincial_gazette", "sheriff", "municipality",
    "bank", "auctioneer", "estate", "insolvency", "portal", "manual_upload", "other",
)

DOCUMENT_TYPES = ("html", "pdf", "text", "csv", "json", "email", "image")

PROPERTY_TYPES = (
    "house", "apartment", "townhouse", "vacant_land", "farm",
    "commercial", "industrial", "mixed_use", "sectional_title", "unknown",
)

OPPORTUNITY_TYPES = (
    "sheriff_sale", "bank_repossession", "assisted_sale", "insolvent_estate",
    "deceased_estate", "municipal_disposal", "authorised_auction", "urgent_sale", "other",
)

OPPORTUNITY_STATUSES = (
    "new", "needs_review", "shortlisted", "verification_pending", "verified",
    "rejected", "postponed", "cancelled", "sold", "expired",
)

CONTACT_TYPES = (
    "sheriff", "bank", "estate_agent", "auctioneer", "executor", "trustee",
    "liquidator", "municipality", "attorney", "other",
)

RISK_SEVERITIES = ("low", "medium", "high", "critical")

DUE_DILIGENCE_STATUSES = ("not_started", "in_progress", "blocked", "complete", "not_applicable")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(32))
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(128), nullable=True)
    access_method: Mapped[str] = mapped_column(String(32), default="manual_upload")
    collector_name: Mapped[str] = mapped_column(String(64), default="manual_upload")
    parser_name: Mapped[str] = mapped_column(String(64), default="sheriff_notice_parser")
    collection_frequency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Section 19 compliance record
    robots_policy_checked: Mapped[bool] = mapped_column(default=False)
    terms_checked: Mapped[bool] = mapped_column(default=False)
    automated_access_allowed: Mapped[bool] = mapped_column(default=False)
    legal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    collection_runs: Mapped[list[CollectionRun]] = relationship(back_populates="source")


class CollectionRun(Base):
    __tablename__ = "collection_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    items_found: Mapped[int] = mapped_column(default=0)
    documents_created: Mapped[int] = mapped_column(default=0)
    opportunities_created: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="collection_runs")


class RawDocument(Base):
    __tablename__ = "raw_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    collection_run_id: Mapped[str | None] = mapped_column(ForeignKey("collection_runs.id"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    document_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    original_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(32), default="pending")
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    source_listings: Mapped[list[SourceListing]] = relationship(back_populates="raw_document")


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    canonical_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    suburb: Mapped[str | None] = mapped_column(String(128), nullable=True)
    town: Mapped[str | None] = mapped_column(String(128), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(128), nullable=True)
    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    country: Mapped[str] = mapped_column(String(64), default="South Africa")

    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    geocode_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)

    erf_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    portion_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    farm_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    farm_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    township: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extension: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sectional_title_scheme: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sectional_unit_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    deeds_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    property_type: Mapped[str] = mapped_column(String(32), default="unknown")
    estimated_land_area_m2: Mapped[float | None] = mapped_column(nullable=True)
    estimated_floor_area_m2: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    opportunities: Mapped[list[Opportunity]] = relationship(back_populates="property_")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"))
    opportunity_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new")

    province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(128), nullable=True)

    case_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    auction_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auction_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    auction_venue: Mapped[str | None] = mapped_column(String(500), nullable=True)
    closing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspection_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reserve_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    asking_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    deposit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    deposit_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    buyer_premium_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    vat_applicable: Mapped[str | None] = mapped_column(String(16), nullable=True)  # yes/no/unknown

    improvements_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    conditions_of_sale_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occupation_status: Mapped[str] = mapped_column(String(32), default="unknown")

    source_confidence: Mapped[str] = mapped_column(String(16), default="unknown")
    extraction_confidence: Mapped[float] = mapped_column(default=0.0)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    property_: Mapped[Property] = relationship(back_populates="opportunities")
    source_listings: Mapped[list[SourceListing]] = relationship(back_populates="opportunity")
    contacts: Mapped[list[Contact]] = relationship(back_populates="opportunity")
    risk_flags: Mapped[list[RiskFlag]] = relationship(back_populates="opportunity")
    scores: Mapped[list[Score]] = relationship(back_populates="opportunity")
    due_diligence_items: Mapped[list[DueDiligenceItem]] = relationship(back_populates="opportunity")

    def latest_score(self) -> Score | None:
        return max(self.scores, key=lambda s: s.calculated_at) if self.scores else None


class SourceListing(Base):
    __tablename__ = "source_listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"))
    raw_document_id: Mapped[str] = mapped_column(ForeignKey("raw_documents.id"))
    external_listing_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_status: Mapped[str] = mapped_column(String(32), default="active")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    raw_extracted_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extraction_confidence: Mapped[float] = mapped_column(default=0.0)

    opportunity: Mapped[Opportunity] = relationship(back_populates="source_listings")
    raw_document: Mapped[RawDocument] = relationship(back_populates="source_listings")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"))
    contact_type: Mapped[str] = mapped_column(String(32))
    organisation_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    person_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_public_contact: Mapped[bool] = mapped_column(default=True)

    opportunity: Mapped[Opportunity] = relationship(back_populates="contacts")


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"))
    code: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opportunity: Mapped[Opportunity] = relationship(back_populates="risk_flags")


class Score(Base):
    __tablename__ = "scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"))
    scoring_version: Mapped[str] = mapped_column(String(32))
    opportunity_score: Mapped[float] = mapped_column()
    risk_score: Mapped[float] = mapped_column()
    completeness_score: Mapped[float] = mapped_column()
    component_breakdown: Mapped[dict] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    opportunity: Mapped[Opportunity] = relationship(back_populates="scores")


class DueDiligenceItem(Base):
    __tablename__ = "due_diligence_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    opportunity_id: Mapped[str] = mapped_column(ForeignKey("opportunities.id"))
    category: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="not_started")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    opportunity: Mapped[Opportunity] = relationship(back_populates="due_diligence_items")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
