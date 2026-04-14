const orchestrator = require("./orchestrator");
const config = require("./config");

/**
 * Central remediation dispatcher.
 *
 * Each handler receives the parsed AppSignal alert payload and decides
 * which Orchestrator action to trigger. All actions are logged with
 * timestamps for the audit trail.
 *
 * Metric name → handler mapping:
 *
 *   uipath.jobs.faulted_rate   → restartFaultedProcess
 *   uipath.queue.pending       → requeueFailedItems
 *   uipath.queue.failed_rate   → requeueFailedItems
 *   uipath.robots.disconnected → escalateToHuman
 *   uipath.robots.utilization  → escalateToHuman
 *   uipath.collector.poll_success → escalateToHuman (collector is down)
 *   default                    → escalateToHuman
 */
async function dispatch(alert) {
  const { metric, tags, value, threshold, trigger } = alert;

  console.log(
    `[remediation] Dispatching — metric=${metric} value=${value} threshold=${threshold}`
  );

  const auditEntry = {
    timestamp: new Date().toISOString(),
    metric,
    value,
    threshold,
    trigger,
    tags,
    action: null,
    result: null,
    error: null,
  };

  try {
    if (metric.startsWith("uipath.jobs.faulted_rate")) {
      auditEntry.action = "restart_faulted_process";
      auditEntry.result = await restartFaultedProcess(tags);
    } else if (
      metric === "uipath.queue.pending" ||
      metric === "uipath.queue.failed_rate"
    ) {
      auditEntry.action = "requeue_failed_items";
      auditEntry.result = await requeueFailedItems(tags);
    } else if (metric.startsWith("uipath.robots.disconnected")) {
      auditEntry.action = "escalate_disconnected_robots";
      auditEntry.result = await escalateToHuman(alert, "Robots disconnected");
    } else if (metric === "uipath.collector.poll_success") {
      auditEntry.action = "escalate_collector_down";
      auditEntry.result = await escalateToHuman(alert, "RPAWatch collector is down");
    } else {
      auditEntry.action = "escalate_unknown";
      auditEntry.result = await escalateToHuman(alert, "Unknown alert");
    }

    console.log(`[remediation] Complete — action=${auditEntry.action}`);
  } catch (err) {
    auditEntry.error = err.message;
    console.error(`[remediation] Failed — ${err.message}`);
    // Always escalate to human if automated remediation fails
    try {
      await escalateToHuman(alert, `Automated remediation failed: ${err.message}`);
    } catch (escalateErr) {
      console.error(`[remediation] Escalation also failed — ${escalateErr.message}`);
    }
  }

  logAudit(auditEntry);
  return auditEntry;
}

// ------------------------------------------------------------------ //
//  Handlers                                                             //
// ------------------------------------------------------------------ //

/**
 * Stops any lingering running jobs for the faulted process,
 * then restarts it via the RPAWatch_RestartFaultedJob process.
 */
async function restartFaultedProcess(tags) {
  const processName = tags?.process;
  if (!processName) {
    throw new Error("Cannot restart: no process name in alert tags");
  }

  // Soft-stop running instances first to avoid duplicate execution
  await orchestrator.stopRunningJobs(processName);

  // Trigger restart workflow
  const job = await orchestrator.startProcess(
    config.uipath.processes.restartJob,
    { TargetProcessName: processName }
  );

  return { restarted: true, jobId: job?.Id, processName };
}

/**
 * Retries all failed queue items for the alerted queue,
 * then starts the queue processor if it's not running.
 */
async function requeueFailedItems(tags) {
  const queueName = tags?.queue;
  if (!queueName) {
    throw new Error("Cannot requeue: no queue name in alert tags");
  }

  const result = await orchestrator.requeueFailedItems(queueName);

  // Start the requeue orchestration process
  const job = await orchestrator.startProcess(
    config.uipath.processes.requeueItems,
    { TargetQueueName: queueName }
  );

  return { ...result, jobId: job?.Id, queueName };
}

/**
 * Triggers the human escalation process in Orchestrator,
 * passing full alert context as input arguments so the
 * escalation workflow can create a ticket or send a notification.
 */
async function escalateToHuman(alert, reason) {
  const job = await orchestrator.startProcess(
    config.uipath.processes.escalate,
    {
      AlertMetric: alert.metric,
      AlertValue: String(alert.value),
      AlertThreshold: String(alert.threshold),
      AlertReason: reason,
      AlertTrigger: alert.trigger || "",
      AlertTags: JSON.stringify(alert.tags || {}),
    }
  );

  return { escalated: true, jobId: job?.Id, reason };
}

// ------------------------------------------------------------------ //
//  Audit log                                                            //
// ------------------------------------------------------------------ //

/**
 * Writes a structured audit entry to stdout.
 * In production, pipe this to a log aggregator or write to a file.
 * The audit trail is important for government compliance (FISMA).
 */
function logAudit(entry) {
  console.log("[AUDIT]", JSON.stringify(entry));
}

module.exports = { dispatch };
