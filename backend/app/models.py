from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .enums import (
    MaintenanceKind,
    ReservationMode,
    ReservationStatus,
    ServiceActionKind,
)


class Base(DeclarativeBase):
    pass


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    connector_type: Mapped[str] = mapped_column(String(16))
    max_power_kw: Mapped[float] = mapped_column(Numeric(6, 2))
    accessible: Mapped[bool] = mapped_column(Boolean, default=False)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="vehicle")


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    location: Mapped[str] = mapped_column(String(128))

    connectors: Mapped[list["Connector"]] = relationship(
        back_populates="site", cascade="all, delete-orphan"
    )


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    code: Mapped[str] = mapped_column(String(16))
    connector_type: Mapped[str] = mapped_column(String(16))
    # 枪口额定/当前可用功率上限（kW）。维护降额通过维护窗口的 effective_power_kw 叠加
    rated_power_kw: Mapped[float] = mapped_column(Numeric(6, 2))
    accessible: Mapped[bool] = mapped_column(Boolean, default=False)
    position_note: Mapped[str] = mapped_column(String(255), default="")

    site: Mapped[Site] = relationship(back_populates="connectors")
    maintenance_windows: Mapped[list["MaintenanceWindow"]] = relationship(
        back_populates="connector", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_connector_site_code"),)


class MaintenanceWindow(Base):
    """运营端记录的降额/停用/恢复生效时段。

    恢复 = 给此前的降额/停用窗口设置实际结束时刻（ended_at），
    窗口本身保留，作为历史审计与“按真实交集判断影响”的依据。
    """

    __tablename__ = "maintenance_windows"

    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int] = mapped_column(ForeignKey("connectors.id"))
    kind: Mapped[MaintenanceKind] = mapped_column(Enum(MaintenanceKind))
    start_at: Mapped[datetime] = mapped_column(DateTime)
    planned_end_at: Mapped[datetime] = mapped_column(DateTime)
    # 提前恢复时写入实际结束时刻；为空表示仍在生效
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 降额后的功率；停用窗口为空
    effective_power_kw: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    reason: Mapped[str] = mapped_column(String(255), default="")

    connector: Mapped[Connector] = relationship(back_populates="maintenance_windows")


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(primary_key=True)
    ref: Mapped[str] = mapped_column(String(32), unique=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"))
    mode: Mapped[ReservationMode] = mapped_column(Enum(ReservationMode))
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.CONFIRMED
    )
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    min_power_kw: Mapped[float] = mapped_column(Numeric(6, 2))
    # 固定枪口模式：确认时锁定；资源池模式：确认时为空，到站分配
    connector_id: Mapped[int | None] = mapped_column(
        ForeignKey("connectors.id"), nullable=True
    )
    # 确认时的承诺快照（插头/功率/无障碍/锁定枪口或池名额），后续任何变化不得改写
    confirmation_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now()
    )

    vehicle: Mapped[Vehicle] = relationship(back_populates="reservations", foreign_keys=[vehicle_id])
    connector: Mapped[Connector | None] = relationship(foreign_keys=[connector_id])
    events: Mapped[list["ReservationEvent"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan",
        order_by="ReservationEvent.id",
    )
    service_actions: Mapped[list["ServiceAction"]] = relationship(
        back_populates="reservation", cascade="all, delete-orphan"
    )


class ReservationEvent(Base):
    """订单生命周期事件流，所有转换与维护影响均留痕。"""

    __tablename__ = "reservation_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"))
    event_type: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now()
    )

    reservation: Mapped[Reservation] = relationship(back_populates="events")


class ServiceAction(Base):
    """客服动作：替代枪口/费用调整必须指向当时的订单与设备状态。"""

    __tablename__ = "service_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"))
    kind: Mapped[ServiceActionKind] = mapped_column(Enum(ServiceActionKind))
    # 动作发生时的订单状态与设备状态快照（只读留痕）
    order_status_at_action: Mapped[ReservationStatus] = mapped_column(Enum(ReservationStatus))
    connector_state_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    target_connector_id: Mapped[int | None] = mapped_column(
        ForeignKey("connectors.id"), nullable=True
    )
    amount: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    note: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now()
    )

    reservation: Mapped[Reservation] = relationship(back_populates="service_actions")
    target_connector: Mapped[Connector | None] = relationship(foreign_keys=[target_connector_id])


class IdempotencyRecord(Base):
    """幂等键 -> 首次请求的响应内容；重复提交原样返回。"""

    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    request_path: Mapped[str] = mapped_column(String(128))
    response_code: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now()
    )
