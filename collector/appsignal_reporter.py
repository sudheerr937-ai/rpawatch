import logging

from appsignal import Appsignal
from appsignal.metrics import add_distribution_value, increment_counter, set_gauge

from .config import AppSignalConfig
from .metrics_transformer import JobMetrics, QueueMetrics, RobotMetrics

logger = logging.getLogger(__name__)


class AppSignalReporter:
    """
    Pushes RPA health metrics to AppSignal as gauges, counters,
    and distribution values. All metrics are namespaced under
    'uipath.*' for easy filtering in AppSignal dashboards.
    """

    def __init__(self, config: AppSignalConfig):
        self.appsignal = Appsignal(
            active=True,
            name=config.app_name,
            push_api_key=config.push_api_key,
        )
        self.appsignal.start()
        logger.info("AppSignal reporter initialised — app: %s", config.app_name)

    # ------------------------------------------------------------------ #
    #  Jobs                                                                 #
    # ------------------------------------------------------------------ #

    def report_jobs(self, job_metrics: list[JobMetrics]):
        for m in job_metrics:
            tags = {"process": m.process_name}

            # Current snapshot gauges
            set_gauge("uipath.jobs.total", float(m.total), tags)
            set_gauge("uipath.jobs.successful", float(m.successful), tags)
            set_gauge("uipath.jobs.faulted", float(m.faulted), tags)
            set_gauge("uipath.jobs.stopped", float(m.stopped), tags)
            set_gauge("uipath.jobs.running", float(m.running), tags)

            # Rate — most useful for alert thresholds
            # e.g. alert when uipath.jobs.faulted_rate > 20%
            set_gauge("uipath.jobs.faulted_rate", m.faulted_rate, tags)

            # Distribution for percentile tracking in AppSignal
            if m.avg_duration_seconds > 0:
                add_distribution_value(
                    "uipath.jobs.duration_seconds",
                    m.avg_duration_seconds,
                    tags,
                )

            logger.debug(
                "Jobs reported — process=%s total=%d faulted=%d faulted_rate=%.1f%%",
                m.process_name, m.total, m.faulted, m.faulted_rate,
            )

    # ------------------------------------------------------------------ #
    #  Queues                                                               #
    # ------------------------------------------------------------------ #

    def report_queues(self, queue_metrics: list[QueueMetrics]):
        for m in queue_metrics:
            tags = {"queue": m.queue_name}

            set_gauge("uipath.queue.pending", float(m.pending), tags)
            set_gauge("uipath.queue.in_progress", float(m.in_progress), tags)
            set_gauge("uipath.queue.failed", float(m.failed), tags)
            set_gauge("uipath.queue.retried", float(m.retried), tags)

            # Alert on this: e.g. queue failure rate > 15%
            set_gauge("uipath.queue.failed_rate", m.failed_rate, tags)

            # Pending depth is the most actionable queue signal —
            # a growing backlog means robots are not keeping up
            logger.debug(
                "Queue reported — queue=%s pending=%d failed=%d failed_rate=%.1f%%",
                m.queue_name, m.pending, m.failed, m.failed_rate,
            )

    # ------------------------------------------------------------------ #
    #  Robots                                                               #
    # ------------------------------------------------------------------ #

    def report_robots(self, robot_metrics: RobotMetrics):
        set_gauge("uipath.robots.available", float(robot_metrics.available))
        set_gauge("uipath.robots.busy", float(robot_metrics.busy))
        set_gauge("uipath.robots.disconnected", float(robot_metrics.disconnected))
        set_gauge("uipath.robots.unresponsive", float(robot_metrics.unresponsive))
        set_gauge("uipath.robots.utilization_rate", robot_metrics.utilization_rate)

        # A disconnected robot count > 0 is a critical alert candidate
        if robot_metrics.disconnected > 0:
            logger.warning(
                "%d robot(s) are disconnected.", robot_metrics.disconnected
            )

        logger.debug(
            "Robots reported — available=%d busy=%d disconnected=%d utilization=%.1f%%",
            robot_metrics.available,
            robot_metrics.busy,
            robot_metrics.disconnected,
            robot_metrics.utilization_rate,
        )

    # ------------------------------------------------------------------ #
    #  Collector health                                                     #
    # ------------------------------------------------------------------ #

    def report_collector_health(self, success: bool, duration_ms: float):
        """
        Tracks the health of the collector itself. Use this to alert
        if the collector stops running or takes too long to poll.
        """
        set_gauge("uipath.collector.poll_success", 1.0 if success else 0.0)
        add_distribution_value("uipath.collector.poll_duration_ms", duration_ms)
