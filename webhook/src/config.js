require("dotenv").config();

function required(name) {
  const val = process.env[name];
  if (!val) throw new Error(`Missing required env variable: ${name}`);
  return val;
}

const config = {
  server: {
    port: parseInt(process.env.PORT || "3000"),
    webhookSecret: process.env.WEBHOOK_SECRET || null,
  },

  uipath: {
    mode: (process.env.UIPATH_MODE || "cloud").toLowerCase(),

    // Cloud
    clientId: process.env.UIPATH_CLIENT_ID,
    clientSecret: process.env.UIPATH_CLIENT_SECRET,
    organization: process.env.UIPATH_ORGANIZATION,
    tenant: process.env.UIPATH_TENANT,

    // On-prem
    baseUrl: process.env.UIPATH_BASE_URL,
    username: process.env.UIPATH_USERNAME,
    password: process.env.UIPATH_PASSWORD,
    tenancyName: process.env.UIPATH_TENANCY_NAME || "Default",

    // Common
    folderId: process.env.UIPATH_FOLDER_ID || null,

    // Remediation process names in your Orchestrator
    processes: {
      restartJob:
        process.env.UIPATH_PROCESS_RESTART || "RPAWatch_RestartFaultedJob",
      requeueItems:
        process.env.UIPATH_PROCESS_REQUEUE || "RPAWatch_RequeueFailedItems",
      escalate:
        process.env.UIPATH_PROCESS_ESCALATE || "RPAWatch_EscalateToHuman",
    },
  },
};

module.exports = config;
