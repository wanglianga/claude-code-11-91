from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from .enums import (
    ImpactDecision,
    MaintenanceKind,
    ReservationMode,
    ReservationStatus,
    ServiceActionKind,
)

# 数据库用 Numeric 保证精度，API 统一以 JSON number 输出
DecimalNum = Annotated[
    Decimal,
    PlainSerializer(lambda v: float(v) if v is not None else None, return_type=float | None),
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- 基础资源 ----------

class VehicleOut(ORMModel):
    id: int
    name: str
    connector_type: str
    max_power_kw: DecimalNum
    accessible: bool


class ConnectorOut(ORMModel):
    id: int
    code: str
    connector_type: str
    rated_power_kw: DecimalNum
    accessible: bool
    position_note: str


class SiteOut(ORMModel):
    id: int
    name: str
    location: str
    connectors: list[ConnectorOut]


# ---------- 候选搜索 ----------

class SearchRequest(BaseModel):
    vehicle_id: int
    site_id: int
    start_at: datetime
    duration_minutes: int = Field(gt=0, le=600)
    min_power_kw: float = Field(gt=0)
    mode: ReservationMode = ReservationMode.CONNECTOR


class RejectReason(BaseModel):
    connector_code: str
    reasons: list[str]


class SegmentInfo(BaseModel):
    start_at: datetime
    end_at: datetime
    available_power_kw: float
    note: str = ""


class ConnectorCandidate(BaseModel):
    connector_id: int
    connector_code: str
    eligible: bool
    effective_power_kw: float          # 时间窗内最差（最小）有效功率
    locked_by_ref: str | None = None   # 被哪笔有效预约占用
    segments: list[SegmentInfo]
    reasons: list[str]                 # 不合格原因


class PoolCandidate(BaseModel):
    site_id: int
    mode: ReservationMode
    eligible: bool
    # 时间窗内可同时履约的最少合格枪数（容量瓶颈）
    confirmable_slots: int
    window_segments: list[SegmentInfo]
    connector_candidates: list[ConnectorCandidate]


# ---------- 预约 ----------

class ConfirmRequest(BaseModel):
    vehicle_id: int
    site_id: int
    start_at: datetime
    duration_minutes: int = Field(gt=0, le=600)
    min_power_kw: float = Field(gt=0)
    mode: ReservationMode = ReservationMode.CONNECTOR
    # 固定枪口模式可指定偏好枪口；为空时由后端选择一支合格枪并锁住
    preferred_connector_id: int | None = None
    idempotency_key: str = Field(min_length=8, max_length=64)


class ReservationEventOut(ORMModel):
    id: int
    event_type: str
    detail: str
    created_at: datetime


class ServiceActionOut(ORMModel):
    id: int
    kind: ServiceActionKind
    order_status_at_action: ReservationStatus
    connector_state_snapshot: str
    target_connector_id: int | None
    amount: DecimalNum | None
    note: str
    created_at: datetime


class ReservationOut(ORMModel):
    id: int
    ref: str
    vehicle_id: int
    site_id: int
    mode: ReservationMode
    status: ReservationStatus
    start_at: datetime
    end_at: datetime
    min_power_kw: DecimalNum
    connector_id: int | None
    confirmation_snapshot: str
    created_at: datetime
    events: list[ReservationEventOut] = []
    service_actions: list[ServiceActionOut] = []


class TransitionRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=64)


# ---------- 维护 ----------

class MaintenanceCreate(BaseModel):
    connector_id: int
    kind: MaintenanceKind
    start_at: datetime
    planned_end_at: datetime
    effective_power_kw: float | None = None
    reason: str = ""
    idempotency_key: str = Field(min_length=8, max_length=64)


class MaintenanceRecover(BaseModel):
    ended_at: datetime
    idempotency_key: str = Field(min_length=8, max_length=64)


class MaintenanceOut(ORMModel):
    id: int
    connector_id: int
    kind: MaintenanceKind
    start_at: datetime
    planned_end_at: datetime
    ended_at: datetime | None
    effective_power_kw: DecimalNum | None
    reason: str


class ImpactItem(BaseModel):
    reservation_id: int
    ref: str
    status: ReservationStatus
    mode: ReservationMode
    connector_id: int | None
    decision: ImpactDecision
    reason: str
    overlap_start: datetime | None
    overlap_end: datetime | None


class MaintenanceImpactOut(BaseModel):
    maintenance: MaintenanceOut
    impacts: list[ImpactItem]


# ---------- 客服动作 ----------

class ServiceActionCreate(BaseModel):
    reservation_id: int
    kind: ServiceActionKind
    target_connector_id: int | None = None
    amount: float | None = None
    note: str = ""
    idempotency_key: str = Field(min_length=8, max_length=64)
