import enum


class ConnectorType(str, enum.Enum):
    CCS = "CCS"
    CHADEMO = "CHAdeMO"
    GBT = "GBT"


class MaintenanceKind(str, enum.Enum):
    DERATE = "DERATE"          # 降额：枪口可用但功率下调
    OUTAGE = "OUTAGE"          # 停用：窗口内完全不可用


class ReservationMode(str, enum.Enum):
    CONNECTOR = "CONNECTOR"    # 固定枪口：确认即锁定具体枪口
    POOL = "POOL"              # 资源池：只承诺名额，到站再分配枪口


class ReservationStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"                    # 已确认，持有容量
    ARRIVED = "ARRIVED"                        # 已到站（池模式此时分配枪口）
    CHARGING = "CHARGING"                      # 充电中，预约管理不可直接释放
    COMPLETED = "COMPLETED"                    # 已完成
    CANCELLED = "CANCELLED"                    # 已取消，释放容量
    NO_SHOW = "NO_SHOW"                        # 迟到失约，释放容量
    NEEDS_RESELECTION = "NEEDS_RESELECTION"    # 维护影响：需改选
    MANUAL_CONTACT = "MANUAL_CONTACT"          # 维护影响：需人工联系


# 仍持有服务容量、会在容量计算中占位的状态
HOLDING_STATUSES = (
    ReservationStatus.CONFIRMED,
    ReservationStatus.ARRIVED,
    ReservationStatus.CHARGING,
)


class ServiceActionKind(str, enum.Enum):
    ALTERNATIVE_CONNECTOR = "ALTERNATIVE_CONNECTOR"  # 客服指定替代枪口
    FEE_ADJUSTMENT = "FEE_ADJUSTMENT"                # 费用调整
    NOTE = "NOTE"                                    # 人工联系备注


class ImpactDecision(str, enum.Enum):
    UNCHANGED = "UNCHANGED"                      # 仍能履约，订单不动
    NEEDS_RESELECTION = "NEEDS_RESELECTION"      # 进入改选
    MANUAL_CONTACT = "MANUAL_CONTACT"            # 已到站，人工联系
    PROTECTED_CHARGING = "PROTECTED_CHARGING"    # 充电中，受保护不可释放
