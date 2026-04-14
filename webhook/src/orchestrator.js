const axios = require("axios");
const config = require("./config");

const CLOUD_AUTH_URL = "https://account.uipath.com/oauth/token";

class OrchestratorClient {
  constructor() {
    this.token = null;
    this.tokenExpiry = 0;
    this.cfg = config.uipath;
  }

  // ------------------------------------------------------------------ //
  //  Authentication                                                       //
  // ------------------------------------------------------------------ //

  async ensureAuthenticated() {
    if (this.token && Date.now() < this.tokenExpiry - 60000) return;
    if (this.cfg.mode === "cloud") {
      await this._authCloud();
    } else {
      await this._authOnPrem();
    }
  }

  async _authCloud() {
    const resp = await axios.post(CLOUD_AUTH_URL, {
      grant_type: "client_credentials",
      client_id: this.cfg.clientId,
      client_secret: this.cfg.clientSecret,
      audience: "https://orchestrator.cloud.uipath.com",
    });
    this.token = resp.data.access_token;
    this.tokenExpiry = Date.now() + resp.data.expires_in * 1000;
    console.log("[auth] Authenticated with UiPath Automation Cloud");
  }

  async _authOnPrem() {
    const resp = await axios.post(
      `${this.cfg.baseUrl}/api/account/authenticate`,
      {
        tenancyName: this.cfg.tenancyName,
        usernameOrEmailAddress: this.cfg.username,
        password: this.cfg.password,
      }
    );
    this.token = resp.data.result;
    this.tokenExpiry = Date.now() + 30 * 60 * 1000; // 30 min
    console.log("[auth] Authenticated with On-Premises Orchestrator");
  }

  get apiBase() {
    if (this.cfg.mode === "cloud") {
      return `https://cloud.uipath.com/${this.cfg.organization}/${this.cfg.tenant}/orchestrator_/odata`;
    }
    return `${this.cfg.baseUrl}/odata`;
  }

  get headers() {
    const h = { Authorization: `Bearer ${this.token}` };
    if (this.cfg.folderId) {
      h["X-UIPATH-OrganizationUnitId"] = this.cfg.folderId;
    }
    return h;
  }

  // ------------------------------------------------------------------ //
  //  Job actions                                                          //
  // ------------------------------------------------------------------ //

  /**
   * Starts a named process in Orchestrator with an optional input argument
   * map. Used by all remediation handlers to trigger recovery workflows.
   */
  async startProcess(processName, inputArguments = {}) {
    await this.ensureAuthenticated();

    // 1. Resolve release key from process name
    const releaseResp = await axios.get(`${this.apiBase}/Releases`, {
      headers: this.headers,
      params: {
        $filter: `Name eq '${processName}'`,
        $select: "Key,Name",
        $top: 1,
      },
    });

    const releases = releaseResp.data.value;
    if (!releases || releases.length === 0) {
      throw new Error(
        `Process "${processName}" not found in Orchestrator. ` +
          `Make sure the process is published and the name matches exactly.`
      );
    }

    const releaseKey = releases[0].Key;

    // 2. Start the job
    const jobResp = await axios.post(
      `${this.apiBase}/Jobs/UiPath.Server.Configuration.OData.StartJobs`,
      {
        startInfo: {
          ReleaseKey: releaseKey,
          Strategy: "All",
          JobsCount: 1,
          InputArguments: JSON.stringify(inputArguments),
        },
      },
      { headers: this.headers }
    );

    const job = jobResp.data.value?.[0];
    console.log(
      `[orchestrator] Started process "${processName}" — job id: ${job?.Id}`
    );
    return job;
  }

  /**
   * Retries all failed queue items in the named queue.
   */
  async requeueFailedItems(queueName) {
    await this.ensureAuthenticated();

    // Get failed items
    const resp = await axios.get(`${this.apiBase}/QueueItems`, {
      headers: this.headers,
      params: {
        $filter: `Status eq 'Failed' and QueueDefinitionName eq '${queueName}'`,
        $select: "Id",
        $top: 100,
      },
    });

    const items = resp.data.value || [];
    if (items.length === 0) {
      console.log(`[orchestrator] No failed items found in queue "${queueName}"`);
      return { requeued: 0 };
    }

    // Bulk retry
    await axios.post(
      `${this.apiBase}/QueueItems/UiPath.Server.Configuration.OData.RetryQueueItems`,
      { queueItemIds: items.map((i) => i.Id) },
      { headers: this.headers }
    );

    console.log(
      `[orchestrator] Requeued ${items.length} failed items in "${queueName}"`
    );
    return { requeued: items.length };
  }

  /**
   * Stops all running jobs for a named process (used before restart).
   */
  async stopRunningJobs(processName) {
    await this.ensureAuthenticated();

    const resp = await axios.get(`${this.apiBase}/Jobs`, {
      headers: this.headers,
      params: {
        $filter: `ReleaseName eq '${processName}' and (State eq 'Running' or State eq 'Pending')`,
        $select: "Id,State",
      },
    });

    const jobs = resp.data.value || [];
    for (const job of jobs) {
      await axios.post(
        `${this.apiBase}/Jobs(${job.Id})/UiPath.Server.Configuration.OData.StopJob`,
        { strategy: "SoftStop" },
        { headers: this.headers }
      );
    }

    console.log(
      `[orchestrator] Stopped ${jobs.length} running jobs for "${processName}"`
    );
    return { stopped: jobs.length };
  }
}

module.exports = new OrchestratorClient();
