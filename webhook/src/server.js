const express = require("express");
const config = require("./config");
const { dispatch } = require("./remediation");

const app = express();
app.use(express.json());

// ------------------------------------------------------------------ //
//  Request logging middleware                                           //
// ------------------------------------------------------------------ //

app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// ------------------------------------------------------------------ //
//  Optional webhook secret validation                                  //
//  Set WEBHOOK_SECRET in .env to enable — recommended for production  //
// ------------------------------------------------------------------ //

function validateSecret(req, res, next) {
  if (!config.server.webhookSecret) return next();
  const provided = req.headers["x-webhook-secret"] || req.query.secret;
  if (provided !== config.server.webhookSecret) {
    console.warn("[security] Rejected webhook — invalid secret");
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
}

// ------------------------------------------------------------------ //
//  Health check — used by Docker / uptime monitors                    //
// ------------------------------------------------------------------ //

app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "rpawatch-webhook", ts: new Date().toISOString() });
});

// ------------------------------------------------------------------ //
//  Main webhook endpoint                                               //
//                                                                      //
//  Configure AppSignal to POST alerts to:                             //
//    http://your-server:3000/webhook/appsignal                        //
//                                                                      //
//  AppSignal webhook payload shape:                                   //
//  {                                                                   //
//    "marker": { "type": "alert" },                                   //
//    "alert": {                                                        //
//      "name": "uipath.jobs.faulted_rate",                            //
//      "trigger_value": 35.5,                                         //
//      "threshold": 20,                                               //
//      "trigger": "above_threshold",                                  //
//      "tags": { "process": "InvoiceProcessor" }                      //
//    }                                                                 //
//  }                                                                   //
// ------------------------------------------------------------------ //

app.post("/webhook/appsignal", validateSecret, async (req, res) => {
  const body = req.body;

  // Acknowledge immediately — AppSignal expects a fast 200
  // Remediation runs async so it doesn't block the response
  res.status(200).json({ received: true });

  // Parse the AppSignal payload into our internal alert shape
  const alert = parseAppSignalPayload(body);
  if (!alert) {
    console.warn("[webhook] Could not parse payload — skipping remediation");
    console.warn("[webhook] Raw payload:", JSON.stringify(body));
    return;
  }

  console.log(
    `[webhook] Alert received — metric=${alert.metric} value=${alert.value} tags=${JSON.stringify(alert.tags)}`
  );

  // Dispatch remediation asynchronously
  dispatch(alert).catch((err) => {
    console.error("[webhook] Unhandled dispatch error:", err.message);
  });
});

// ------------------------------------------------------------------ //
//  Test endpoint — simulate an alert without AppSignal               //
//  POST /webhook/test with a JSON body matching internal alert shape  //
// ------------------------------------------------------------------ //

app.post("/webhook/test", async (req, res) => {
  const alert = req.body;
  if (!alert.metric) {
    return res.status(400).json({ error: "Missing 'metric' field" });
  }
  console.log("[test] Simulated alert:", JSON.stringify(alert));
  const result = await dispatch(alert).catch((err) => ({
    error: err.message,
  }));
  res.json({ dispatched: true, result });
});

// ------------------------------------------------------------------ //
//  Payload parser                                                       //
// ------------------------------------------------------------------ //

function parseAppSignalPayload(body) {
  try {
    const alertData = body.alert || body;
    return {
      metric: alertData.name || alertData.metric,
      value: alertData.trigger_value ?? alertData.value ?? 0,
      threshold: alertData.threshold ?? 0,
      trigger: alertData.trigger || "above_threshold",
      tags: alertData.tags || {},
    };
  } catch (err) {
    console.error("[webhook] Parse error:", err.message);
    return null;
  }
}

// ------------------------------------------------------------------ //
//  Start                                                               //
// ------------------------------------------------------------------ //

app.listen(config.server.port, () => {
  console.log(`
  ╔══════════════════════════════════════════════╗
  ║          RPAWatch — Webhook Receiver         ║
  ║                                              ║
  ║  Listening on port ${String(config.server.port).padEnd(26)}║
  ║  Health:  GET  /health                       ║
  ║  Webhook: POST /webhook/appsignal            ║
  ║  Test:    POST /webhook/test                 ║
  ╚══════════════════════════════════════════════╝
  `);
});

module.exports = app;
