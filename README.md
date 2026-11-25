# 充电预约演示系统（Vue 3 + FastAPI + PostgreSQL）

司机按「站点 + 时间窗 + 停留时长 + 最低功率」预约充电，运营方维护枪口并评估对既有预约的影响。
系统同时支持两种预约粒度，并以同一套容量数据给出可核验结论：

- **固定枪口（CONNECTOR）**：确认时锁定一支兼容枪口，位置承诺直观；枪口故障时需迁移订单。
- **资源池（POOL）**：只承诺一个满足插头/功率/无障碍条件的站点名额，到站再分配枪口；
  以「池内同时可履约的枪口数」限制订单，绝不会因为两支枪各自「空闲」就把同一份容量卖两次。

## 一、目录结构

```
.
├── docker-compose.yml          # 一键启动 db + backend + frontend
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── e2e_check.sh            # 题面场景手工 E2E（16 项检查）
│   ├── app/
│   │   ├── main.py             # FastAPI 入口（含 /docs Swagger UI）
│   │   ├── models.py           # 车辆/站点/枪口/维护窗口/预约/事件/客服动作/幂等记录
│   │   ├── enums.py
│   │   ├── schemas.py
│   │   ├── deps.py             # 幂等端点（事务咨询锁 + 首次响应留存与回放）
│   │   ├── seed.py             # 东站 A/B/C/D 四枪等样例数据
│   │   ├── bootstrap.py        # 容器启动：建表，空库才灌种子（可重复执行）
│   │   ├── services/
│   │   │   ├── capacity.py     # 时间切片容量引擎（两种粒度共用）
│   │   │   ├── reservation.py  # 确认/取消/迟到/到站/开始充电 状态机
│   │   │   └── maintenance.py  # 降额/停用/恢复 + 影响判定 + 客服动作
│   │   └── routers/            # resources / search / reservations / operations
│   └── tests/test_scenarios.py # 20 个 pytest 场景用例
└── frontend/
    ├── Dockerfile              # 多阶段构建：vite build → nginx 静态托管 + API 代理
    ├── nginx.conf
    └── src/
        ├── views/DriverView.vue       # 司机端
        └── views/OperationsView.vue   # 运营端
```

## 二、一键启动（Docker，推荐）

前置：本机已安装 Docker 与 Docker Compose。

```bash
docker compose up --build
```

启动后：

| 服务 | 地址 |
| --- | --- |
| 前端（司机端/运营端两个页签） | http://localhost:8080 |
| 后端 API | http://localhost:8000 |
| Swagger UI（接口文档） | http://localhost:8000/docs |
| PostgreSQL | localhost:5432，库/用户/密码均为 `ccdev` |

后端容器启动时会自动建表，并**仅在空库时**灌入样例数据；重复重启不会清空已有数据。
需要恢复初始演示数据时：

```bash
docker compose exec backend python -m app.seed
```

停止并清理数据卷：

```bash
docker compose down -v
```

## 三、本地开发启动（不使用 Docker）

容器内已预装 Python 3.12 / Node 22 / PostgreSQL 18，下面的命令也适用于普通开发机
（自行准备一个可连接的 PostgreSQL 即可）。

### 1. 后端

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 指向你的 PostgreSQL，默认 postgresql+psycopg://ccdev:ccdev@127.0.0.1:5432/ccdev
export DATABASE_URL="postgresql+psycopg://用户:密码@主机:5432/库名"
.venv/bin/python -m app.seed           # 重置并灌入样例数据
.venv/bin/uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev      # http://localhost:8080，/api 已代理到 127.0.0.1:8000
```

## 四、测试数据与「账号」说明

本演示系统不设登录认证（无账号体系），打开页面即可操作，预置数据如下，
相当于固定的测试入口：

- **站点**：东站充电站（id=1），四支枪口
  - **A**：CCS / 120kW / 无障碍 —— 已被有效预约 `R-SEEDA01` 在周五 18:00–18:30 占用
  - **B**：CCS / 120kW / 无障碍 —— 18:00–18:10 唯一剩余的 90kW 合格容量
  - **C**：CCS / **60kW** / 普通车位 —— 功率不足
  - **D**：**CHAdeMO** / 120kW —— 与 CCS 车辆接口不兼容
- **车辆**：
  - V1：CCS / 120kW（持有 A 枪预约的车主）
  - V2：CCS / **最大受电仅 60kW**
  - V3：CCS / 100kW / **有无障碍接入要求**
  - V4：CCS / 150kW（发起 90kW 请求的第二位车主）
- 所有演示时间固定在 **2026-11-27（周五）**，前端表单已预填 18:00。

## 五、本题验证方式（均已实际执行）

### 1. 后端单元/场景测试：20 项全部通过

```bash
cd backend
.venv/bin/python -m pytest tests/ -q
# 结果：20 passed
```

覆盖：候选与限制原因、搜索不产生订单、两种粒度的并发争抢、成功/失败两类幂等回放、
18:10 降额的真实交集判定、整晚订单的部分受影响、取消释放、迟到、池模式到站分配、
充电会话保护、客服替代枪口/费用调整快照、恢复不改写历史、无障碍约束。

### 2. 题面场景 E2E：16 项检查全部通过

先重置数据，再启动后端，然后：

```bash
cd backend
.venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --port 8000 &
bash e2e_check.sh
# 结果：通过 16 项，失败 0 项
```

该脚本用真实 HTTP 请求验证了题面要求的关键结论：

1. 搜索 18:00–18:10、≥90kW：A 显示被 `R-SEEDA01` 占用、B 是唯一合格枪、
   C 功率不足、D 接口不兼容，限制原因逐条返回；
2. 资源池搜索显示池内**只剩 1 个可确认名额**且不指定枪号；
3. 两笔并发确认抢同一最后时段：固定枪口路线 **200 锁定 B + 409 拒绝**；
   资源池路线同样 **一赢一拒**，赢家 `connector_id = null`；
4. 同一幂等键重放只返回原订单（首次失败也会留存并原样回放）；
5. 18:10 起把 B 降到 60kW：18:10 已结束的预约与降额无交集，**不被撤销**；
6. 降额后 18:15 的 90kW 请求无合格容量（409），而只要求 60kW 的车仍可使用 B；
7. 开始充电后对该枪报故障：订单判定 `PROTECTED_CHARGING`、状态保持 `CHARGING`、
   取消请求被拒。

### 3. 前端手工验证

`npm run dev` 后访问 http://localhost:8080：

- 司机端：选车/选时间窗/切换两种粒度 → 「搜索候选」查看每支枪的切片功率与限制原因 →
  「确认预约」→ 用「重放上次请求」验证幂等 → 在订单上执行到站/开始充电/取消；
- 运营端：对 B 枪提交 18:10 起降额 60kW，立即看到受影响订单与真实时间交集；
  可恢复设备、提交替代枪口/费用调整，并在订单事件流中查看全部留痕。

## 六、关键设计与约束的落实

- **候选搜索不构成订单**：`POST /api/search` 为纯只读；真正占用容量只发生在确认事务里。
- **事务内重算 + 并发安全**：确认先取站点级 `pg_advisory_xact_lock`，
  在同一事务内重新计算所有重叠切片后落单；并发请求被串行化，同一份能力不可能卖两次。
- **池容量不重复售卖**：每个时间切片统计「合格且未锁定的枪数 − 在途池预约数」，
  全程取最小值作为可确认名额。
- **幂等**：每个写操作携带 `idempotency_key`；首次请求（含 409 业务失败）的响应码与
  响应体被持久化，重复提交原样返回，同键不同参数返回 409。
- **状态机**：`CONFIRMED → ARRIVED → CHARGING → COMPLETED`，
  以及 `CANCELLED / NO_SHOW`（释放容量）、`NEEDS_RESELECTION / MANUAL_CONTACT`
  （维护影响）；非法转换返回 409。池模式在「到站」时才分配具体枪口。
- **维护按真实交集判定**：维护窗口与预约按半开区间求交集，交集为空则完全不影响；
  整晚订单遇到中途降额时，已履约区间与待履约区间在原因中分别说明。
  仍满足车辆需求的订单继续履约，不满足的进入改选/人工联系。
- **充电会话保护**：`CHARGING` 订单不能被取消、不能被客服替代枪口流程迁移，
  维护只会给出 `PROTECTED_CHARGING` 判定。
- **历史不可改写**：确认时写入承诺快照（枪号/功率/池名额），之后降额、恢复、
  迁移都不会修改它；客服动作固化当时的订单状态与原枪/目标枪设备快照；
  设备恢复只结束维护窗口并追加 `DEVICE_RECOVERED` 事件，不自动回滚订单状态。
