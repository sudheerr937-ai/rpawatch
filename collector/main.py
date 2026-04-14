"""
RPAWatch — Metrics Collector
Polls UiPath Orchestrator (Cloud or On-Prem) every N seconds,
transforms job/queue/robot data into health metrics, and pushes
them to AppSignal for dashboarding and alerting.
"""

import logging
import time

from .appsignal_reporter import AppSignalReporter
from .config import AppSignalConfig, CollectorConfig, OrchestratorConfig
from .metrics_transformer import transform_jobs, transform_queues, transform_robots
from .orchestrator_client import OrchestratorClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("rpawatch")


def run_collection_cycle(
    client: OrchestratorClient,
    reporter: AppSignalReporter,
    config: CollectorConfig,
):
    start = time.time()
    try:
        # 1. Fetch raw data from Orchestrator
        raw_jobs = client.get_jobs_summary(lookback_minutes=config.lookback_minutes)
        raw_queue_defs = client.get_queue_definitions()
        raw_queue_items = client.get_queue_items_summary()
        raw_robots = client.get_robot_sessions()

        # 2. Transform to structured metrics
        job_metrics = transform_jobs(raw_jobs)
        queue_metrics = transform_queues(raw_queue_items, raw_queue_defs)
        robot_metrics = transform_robots(raw_robots)

        # 3. Push to AppSignal
        reporter.report_jobs(job_metrics)
        reporter.report_queues(queue_metrics)
        reporter.report_robots(robot_metrics)

        duration_ms = (time.time() - start) * 1000
        reporter.report_collector_health(success=True, duration_ms=duration_ms)

        logger.info(
            "Collection cycle complete — "
            "%d processes | %d queues | %d robots | %.0fms",
            len(job_metrics),
            len(queue_metrics),
            len(raw_robots),
            duration_ms,
        )

    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        reporter.report_collector_health(success=False, duration_ms=duration_ms)
        logger.error("Collection cycle failed: %s", e, exc_info=True)


def main():
    logger.info("RPAWatch starting up...")

    orchestrator_config = OrchestratorConfig.from_env()
    appsignal_config = AppSignalConfig.from_env()
    collector_config = CollectorConfig.from_env()

    client = OrchestratorClient(orchestrator_config)
    reporter = AppSignalReporter(appsignal_config)

    logger.info(
        "Configuration loaded — mode=%s poll_interval=%ds lookback=%dmin",
        orchestrator_config.mode,
        collector_config.poll_interval_seconds,
        collector_config.lookback_minutes,
    )

    while True:
        run_collection_cycle(client, reporter, collector_config)
        time.sleep(collector_config.poll_interval_seconds)


if __name__ == "__main__":
    main()
