from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobMetrics:
    process_name: str
    total: int = 0
    successful: int = 0
    faulted: int = 0
    stopped: int = 0
    running: int = 0
    faulted_rate: float = 0.0        # percentage
    avg_duration_seconds: float = 0.0


@dataclass
class QueueMetrics:
    queue_name: str
    queue_id: int
    pending: int = 0
    in_progress: int = 0
    failed: int = 0
    retried: int = 0
    failed_rate: float = 0.0         # percentage


@dataclass
class RobotMetrics:
    available: int = 0
    busy: int = 0
    disconnected: int = 0
    unresponsive: int = 0
    utilization_rate: float = 0.0    # busy / (available + busy) * 100


def transform_jobs(raw_jobs: list[dict[str, Any]]) -> list[JobMetrics]:
    """
    Groups raw job records by process name and computes
    per-process health metrics.
    """
    buckets: dict[str, dict] = defaultdict(
        lambda: {
            "total": 0,
            "successful": 0,
            "faulted": 0,
            "stopped": 0,
            "running": 0,
            "durations": [],
        }
    )

    for job in raw_jobs:
        name = job.get("ReleaseName", "Unknown").split("_")[0]  # strip version suffix
        state = job.get("State", "")
        bucket = buckets[name]
        bucket["total"] += 1

        if state == "Successful":
            bucket["successful"] += 1
        elif state == "Faulted":
            bucket["faulted"] += 1
        elif state == "Stopped":
            bucket["stopped"] += 1
        elif state == "Running":
            bucket["running"] += 1

        # Compute duration for completed jobs
        start = job.get("StartTime")
        end = job.get("EndTime")
        if start and end:
            try:
                from datetime import datetime
                fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
                duration = (
                    datetime.strptime(end[:26] + "Z", fmt)
                    - datetime.strptime(start[:26] + "Z", fmt)
                ).total_seconds()
                if duration >= 0:
                    bucket["durations"].append(duration)
            except (ValueError, TypeError):
                pass

    results = []
    for process_name, b in buckets.items():
        total_completed = b["successful"] + b["faulted"] + b["stopped"]
        faulted_rate = (b["faulted"] / total_completed * 100) if total_completed else 0.0
        avg_duration = sum(b["durations"]) / len(b["durations"]) if b["durations"] else 0.0

        results.append(
            JobMetrics(
                process_name=process_name,
                total=b["total"],
                successful=b["successful"],
                faulted=b["faulted"],
                stopped=b["stopped"],
                running=b["running"],
                faulted_rate=round(faulted_rate, 2),
                avg_duration_seconds=round(avg_duration, 2),
            )
        )
    return results


def transform_queues(
    raw_items: list[dict[str, Any]],
    queue_definitions: list[dict[str, Any]],
) -> list[QueueMetrics]:
    """
    Maps raw queue items to per-queue health metrics using
    queue definitions to resolve IDs to human-readable names.
    """
    id_to_name = {q["Id"]: q["Name"] for q in queue_definitions}

    buckets: dict[int, dict] = defaultdict(
        lambda: {"pending": 0, "in_progress": 0, "failed": 0, "retried": 0}
    )

    for item in raw_items:
        qid = item.get("QueueDefinitionId")
        status = item.get("Status", "")
        if qid is None:
            continue
        if status == "New":
            buckets[qid]["pending"] += 1
        elif status == "InProgress":
            buckets[qid]["in_progress"] += 1
        elif status == "Failed":
            buckets[qid]["failed"] += 1
        elif status == "Retried":
            buckets[qid]["retried"] += 1

    results = []
    for qid, b in buckets.items():
        processed = b["failed"] + b["retried"]  # approximate denominator
        failed_rate = (b["failed"] / processed * 100) if processed else 0.0

        results.append(
            QueueMetrics(
                queue_name=id_to_name.get(qid, f"queue_{qid}"),
                queue_id=qid,
                pending=b["pending"],
                in_progress=b["in_progress"],
                failed=b["failed"],
                retried=b["retried"],
                failed_rate=round(failed_rate, 2),
            )
        )
    return results


def transform_robots(raw_sessions: list[dict[str, Any]]) -> RobotMetrics:
    """
    Aggregates individual robot session states into fleet-level counters.
    """
    metrics = RobotMetrics()

    for session in raw_sessions:
        state = (session.get("State") or "").lower()
        connected = session.get("IsConnected", True)

        if not connected or state in ("disconnected", "unavailable"):
            metrics.disconnected += 1
        elif state in ("available", "idle"):
            metrics.available += 1
        elif state in ("busy", "running", "executing"):
            metrics.busy += 1
        elif state in ("unresponsive", "error"):
            metrics.unresponsive += 1

    total_active = metrics.available + metrics.busy
    if total_active > 0:
        metrics.utilization_rate = round(metrics.busy / total_active * 100, 2)

    return metrics
