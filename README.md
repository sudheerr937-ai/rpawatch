# RPAWatch

Open-source observability and self-healing framework that bridges **UiPath Orchestrator** (Cloud and On-Premises) with **AppSignal** to give government and critical infrastructure teams production-grade RPA monitoring.

## Why this exists

Government agencies and critical infrastructure operators are deploying UiPath RPA at scale — but most deployments have no real-time observability. A faulted robot in a benefits-processing pipeline or a utility management workflow can silently fail for hours before anyone notices.

RPAWatch closes that gap by continuously collecting health signals from Orchestrator and pushing them into AppSignal, where you can build dashboards, set alert thresholds, and trigger automated remediation workflows.

---

## Architecture

```
UiPath Orchestrator          RPAWatch Collector         AppSignal
(Cloud or On-Prem)           (Python)
      │                            │                         │
      │  Jobs / Queues / Robots    │   Custom metrics        │
      │ ─────────────────────────► │ ──────────────────────► │
      │  OData API (every 60s)     │                         │
                                                             │
                                                  Dashboards + Alerts
                                                             │
                                                    Webhook fired
                                                             │
                                              RPAWatch Webhook Receiver
                                                    (Node.js)
                                                             │
                                                    UiPath Orchestrator
                                                  (remediation process)
```

---

## Metrics collected

### Jobs
| Metric | Type | Tags | Description |
|---|---|---|---|
| `uipath.jobs.faulted_rate` | Gauge | `process` | % faulted of completed jobs |
| `uipath.jobs.running` | Gauge | `process` | Currently running jobs |
| `uipath.jobs.duration_seconds` | Distribution | `process` | Job execution duration |

### Queues
| Metric | Type | Tags | Description |
|---|---|---|---|
| `uipath.queue.pending` | Gauge | `queue` | Items waiting to be processed |
| `uipath.queue.failed_rate` | Gauge | `queue` | % failed of processed items |

### Robots
| Metric | Type | Description |
|---|---|---|
| `uipath.robots.disconnected` | Gauge | Disconnected robots |
| `uipath.robots.utilization_rate` | Gauge | Fleet utilization % |

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/sudheerr937-ai/rpawatch
cd rpawatch
cp .env.example .env
```

### 2. Get credentials

**AppSignal:** App Settings → Push & Deploy → copy Push API key

**UiPath Personal Access Token:**
1. cloud.uipath.com → Profile → Personal Access Tokens
2. Add Token, name it `RPAWatch`, expiry 365 days
3. Add scopes: OR.Jobs, OR.Queues, OR.Robots, OR.Folders (+ Read variants)
4. Copy token immediately

### 3. Run with Docker
```bash
docker-compose up -d
```

### 4. Run without Docker
```bash
# Collector
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
python -m collector.main

# Webhook receiver
cd webhook && npm install && npm start
```

---

## Remediation workflows

| Process | Trigger | Action |
|---|---|---|
| `RPAWatch_RestartFaultedJob` | Job faulted rate > threshold | Restarts the process |
| `RPAWatch_RequeueFailedItems` | Queue failure rate > threshold | Retries failed items |
| `RPAWatch_EscalateToHuman` | Unrecoverable alert | Creates incident, notifies team |

---

## Testing locally
```bash
curl -X POST http://localhost:3000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{"metric":"uipath.jobs.faulted_rate","value":35,"threshold":20,"tags":{"process":"InvoiceProcessor"}}'
```

---

## Government compliance

- Full audit log for every automated remediation action
- No sensitive data transmitted — only metric names and values
- Deployable on-premises for air-gapped environments
- Designed with FISMA/FedRAMP requirements in mind

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Contributions welcome especially around compliance logging and additional metrics.

---

## License

MIT
