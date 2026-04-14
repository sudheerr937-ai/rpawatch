# RPAWatch

Open-source observability framework that bridges **UiPath Orchestrator** (Cloud
and On-Premises) with **AppSignal** to give government and critical infrastructure
teams production-grade RPA monitoring.

## Why this exists

Government agencies and critical infrastructure operators are deploying UiPath
RPA at scale — but most deployments have no real-time observability. A faulted
robot in a benefits-processing pipeline or a utility management workflow can
silently fail for hours before anyone notices.

RPAWatch closes that gap by continuously collecting health signals from
Orchestrator and pushing them into AppSignal, where you can build dashboards,
set alert thresholds, and trigger automated remediation workflows.

---

## Architecture

```
UiPath Orchestrator               RPAWatch               AppSignal
(Cloud or On-Prem)                (this repo)
      │                                │                           │
      │  Jobs / Queues / Robots        │   Gauges / Counters       │
      │ ──────────────────────────►   │ ────────────────────────► │
      │  OData API (every 60s)        │   Custom metrics API      │
                                                                   │
                                                        Dashboards + Alerts
                                                                   │
                                                          Webhook → UiPath
                                                        (self-healing layer)
```

---

## Metrics collected

### Jobs (`uipath.jobs.*`)
| Metric | Type | Tags | Description |
|---|---|---|---|
| `uipath.jobs.total` | Gauge | `process` | Total jobs in lookback window |
| `uipath.jobs.faulted` | Gauge | `process` | Faulted job count |
| `uipath.jobs.faulted_rate` | Gauge | `process` | % faulted of completed jobs |
| `uipath.jobs.running` | Gauge | `process` | Currently running jobs |
| `uipath.jobs.duration_seconds` | Distribution | `process` | Job execution duration |

### Queues (`uipath.queue.*`)
| Metric | Type | Tags | Description |
|---|---|---|---|
| `uipath.queue.pending` | Gauge | `queue` | Items waiting to be processed |
| `uipath.queue.in_progress` | Gauge | `queue` | Items being processed |
| `uipath.queue.failed` | Gauge | `queue` | Failed items |
| `uipath.queue.failed_rate` | Gauge | `queue` | % failed of processed items |

### Robots (`uipath.robots.*`)
| Metric | Type | Description |
|---|---|---|
| `uipath.robots.available` | Gauge | Available robots |
| `uipath.robots.busy` | Gauge | Currently executing robots |
| `uipath.robots.disconnected` | Gauge | Disconnected robots (critical alert) |
| `uipath.robots.utilization_rate` | Gauge | busy / (available + busy) × 100 |

### Collector health (`uipath.collector.*`)
| Metric | Type | Description |
|---|---|---|
| `uipath.collector.poll_success` | Gauge | 1 = success, 0 = failed poll |
| `uipath.collector.poll_duration_ms` | Distribution | Time to complete one poll cycle |

---

## Recommended AppSignal alert rules

| Metric | Condition | Severity | Why |
|---|---|---|---|
| `uipath.jobs.faulted_rate` | > 20% | Critical | Process is failing at scale |
| `uipath.queue.pending` | > 500 | Warning | Backlog building up |
| `uipath.robots.disconnected` | > 0 | Critical | Robots offline |
| `uipath.robots.utilization_rate` | > 90% | Warning | Fleet at capacity |
| `uipath.collector.poll_success` | = 0 | Critical | Sentinel itself is down |

---

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/your-username/rpawatch
cd rpawatch
cp .env.example .env
# Edit .env with your credentials
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python -m collector.main
```

### 4. Run with Docker

```bash
docker build -t rpawatch .
docker run --env-file .env rpawatch
```

---

## Getting credentials

### AppSignal
1. Log in to AppSignal → App Settings → Push & Deploy → copy your **Push API key**

### UiPath Automation Cloud
1. Go to **Admin → External Applications → Add Application**
2. Select **Confidential application**
3. Add scopes: `OR.Robots OR.Jobs OR.Queues OR.Folders`
4. Copy the **Client ID** and **Client Secret**

### UiPath On-Premises
Use a service account username and password with **Orchestrator API** role.

---

## Contributing

Contributions welcome — especially around additional metrics, FISMA/FedRAMP
compliance logging, and support for additional Orchestrator API versions.

---

## License

MIT
