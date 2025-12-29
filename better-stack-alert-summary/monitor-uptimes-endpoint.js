require("dotenv").config({ path: __dirname + "/.env" });
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const SLACK_WEBHOOK_URL_PRODUCTION = process.env.SLACK_WEBHOOK_URL_PRODUCTION; //#Alerting-Health-Check-Status
const SLACK_WEBHOOK_URL_STAGING = process.env.SLACK_WEBHOOK_URL_STAGING; //#alerting-health-check-staging-status

const BETTERSTACK_API_TOKEN = process.env.BETTERSTACK_API_TOKEN;
const BETTERSTACK_API_URL = "https://uptime.betterstack.com/api/v2/monitors";

// ConfigMap for state persistence (replaces file-based state)
const K8S_NAMESPACE = process.env.K8S_NAMESPACE || "cronjob";
const K8S_CONFIGMAP_NAME = process.env.K8S_CONFIGMAP_NAME || "betterstack-notification-state";
const NO_ALERT_NOTIFICATION_INTERVAL = 24 * 60 * 60 * 1000; // 24 hours in milliseconds

// Check if running in Kubernetes
const isK8s = process.env.KUBERNETES_SERVICE_HOST !== undefined;

const fetchAllMonitors = async () => {
  const allMonitors = [];
  let currentPage = 1;
  let hasMorePages = true;

  while (hasMorePages) {
    try {
      const response = await fetch(
        `${BETTERSTACK_API_URL}?page=${currentPage}`,
        {
          method: "GET",
          headers: {
            Authorization: `Bearer ${BETTERSTACK_API_TOKEN}`,
          },
        },
      );

      if (!response.ok) {
        throw new Error(`Failed to fetch monitors: ${response.statusText}`);
      }

      const data = await response.json();
      allMonitors.push(...data.data);

      // Check if there are more pages
      if (data.pagination && data.pagination.next) {
        currentPage++;
      } else {
        hasMorePages = false;
      }
    } catch (error) {
      console.error("Error fetching monitors:", error);
      hasMorePages = false;
    }
  }

  return allMonitors;
};

const ensureHttps = (url) => {
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return `https://${url}`;
  }
  return url;
};

const categorizeMonitors = (monitors) => {
  const categories = {
    production: [],    // api.mobula.io + explorer-api-2.mobula.io (NOT explorer-api.mobula.io)
    staging: [],       // api.zobula.xyz + explorer-api.mobula.io + explorer-api.zobula.xyz
  };

  monitors.forEach((monitor) => {
    const url = monitor.attributes.url.toLowerCase();

    // IMPORTANT: Check explorer-api-2 BEFORE explorer-api to avoid false matches
    // Production: explorer-api-2.mobula.io
    if (url.includes("explorer-api-2.mobula.io")) {
      categories.production.push(monitor);
    }
    // Explorer API 1 (mobula.io) -> STAGING
    else if (url.includes("explorer-api.mobula.io")) {
      categories.staging.push(monitor);
    }
    // Explorer preprod (zobula.xyz) -> STAGING
    else if (url.includes("explorer-api.zobula.xyz")) {
      categories.staging.push(monitor);
    }
    // Production: api.mobula.io (other api.mobula.io URLs)
    else if (url.includes("api.mobula.io")) {
      categories.production.push(monitor);
    }
    // Staging: api.zobula.xyz
    else if (url.includes("api.zobula.xyz")) {
      categories.staging.push(monitor);
    }
  });

  return categories;
};

const createEnvironmentStatusMessage = (
  monitors,
  environmentName,
  includeDownMonitors = true,
) => {
  const statusCounts = {
    up: 0,
    down: 0,
    paused: 0,
    validating: 0,
  };

  const downMonitors = [];

  monitors.forEach((monitor) => {
    const status = monitor.attributes.status;
    statusCounts[status] = (statusCounts[status] || 0) + 1;

    if (status === "down" && includeDownMonitors) {
      downMonitors.push(monitor);
    }
  });

  const totalMonitors = monitors.length;
  const operationalCount = statusCounts.up || 0;
  const uptimePercentage = ((operationalCount / totalMonitors) * 100).toFixed(
    1,
  );

  // Header with environment name and percentage
  let message = `:warning: ${environmentName.toUpperCase()} Status - ${uptimePercentage}% Operational\n`;
  message += `:bar_chart: ${environmentName.toUpperCase()} Environment Overview - ${
    statusCounts.down || 0
  } Services Down\n`;

  // Status breakdown
  message += `*Total Monitors*\n${totalMonitors}\n`;
  message += `*Operational*\n:small_blue_diamond: ${operationalCount}\n`;
  message += `*Down*\n:small_red_triangle_down: ${statusCounts.down || 0}\n`;
  message += `*Paused*\n:double_vertical_bar: ${statusCounts.paused || 0}\n`;
  message += `*Validating*\n:arrows_counterclockwise: ${
    statusCounts.validating || 0
  }\n`;

  return { message, downMonitors };
};

const createDownMonitorsMessage = (
  downMonitors,
  maxMonitorsPerMessage = 15,
) => {
  if (downMonitors.length === 0) {
    return [""];
  }

  const messages = [];
  const chunks = [];

  // Split into chunks
  for (let i = 0; i < downMonitors.length; i += maxMonitorsPerMessage) {
    chunks.push(downMonitors.slice(i, i + maxMonitorsPerMessage));
  }

  chunks.forEach((chunk, index) => {
    let message = `${
      index === 0
        ? ":red_circle: Service Currently Down\n"
        : ":red_circle: Service Currently Down (continued)\n"
    }`;

    chunk.forEach((monitor) => {
      const name =
        monitor.attributes.pronounceable_name || monitor.attributes.url;
      const monitorId = monitor.id;
      const monitorUrl = ensureHttps(monitor.attributes.url);
      const betterStackUrl = `https://uptime.betterstack.com/team/t161704/monitors/${monitorId}`;

      // Pour les URLs longues (> 100 chars), afficher juste "path" comme hyperlien
      // Sinon afficher l'URL complète
      let pathDisplay;
      if (monitorUrl.length > 100) {
        pathDisplay = `<${monitorUrl}|path>`;
      } else {
        pathDisplay = monitorUrl;
      }

      message += `• <${betterStackUrl}|${name}>\n  path: ${pathDisplay}\n`;
    });

    messages.push(message);
  });

  return messages;
};

const sendSlackAlert = async (webhookUrl, message) => {
  try {
    const response = await fetch(webhookUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: message,
        mrkdwn: true,
      }),
    });

    if (!response.ok) {
      throw new Error(`Slack API error: ${response.statusText}`);
    }

    return true;
  } catch (error) {
    console.error("Error sending Slack alert:", error);
    return false;
  }
};

/**
 * Get state from ConfigMap (K8s) or file (local)
 */
const getState = (key) => {
  try {
    if (isK8s) {
      // Running in Kubernetes - use ConfigMap
      const cmd = `kubectl get configmap ${K8S_CONFIGMAP_NAME} -n ${K8S_NAMESPACE} -o jsonpath='{.data.${key}}'`;
      const result = execSync(cmd, { encoding: "utf8" }).trim();

      if (!result || result === "") {
        return null;
      }

      return JSON.parse(result);
    } else {
      // Running locally - use file
      const stateFile = path.join("/tmp", `betterstack-${key}.json`);
      if (!fs.existsSync(stateFile)) {
        return null;
      }
      return JSON.parse(fs.readFileSync(stateFile, "utf8"));
    }
  } catch (error) {
    console.log(`ℹ️  No existing state for ${key}`);
    return null;
  }
};

/**
 * Update state in ConfigMap (K8s) or file (local)
 */
const updateState = (key, value) => {
  try {
    if (isK8s) {
      // Running in Kubernetes - update ConfigMap
      const data = JSON.stringify(value);
      const cmd = `kubectl patch configmap ${K8S_CONFIGMAP_NAME} -n ${K8S_NAMESPACE} --type merge -p '{"data":{"${key}":"${data.replace(/"/g, '\\"')}"}}'`;
      execSync(cmd);
    } else {
      // Running locally - use file
      const stateFile = path.join("/tmp", `betterstack-${key}.json`);
      fs.writeFileSync(stateFile, JSON.stringify(value, null, 2));
    }
  } catch (error) {
    console.error(`Error updating state for ${key}:`, error.message);
  }
};

/**
 * Check if we should send a notification when there are no alerts
 * Returns true if we should send, false if we should skip (sent within last 24h)
 */
const shouldSendNoAlertNotification = (environment) => {
  try {
    const state = getState(environment);

    if (!state) {
      // No state = never sent before, so send now
      return true;
    }

    const lastNotificationTime = state.lastNotificationTime || 0;
    const now = Date.now();
    const timeSinceLastNotification = now - lastNotificationTime;

    if (timeSinceLastNotification >= NO_ALERT_NOTIFICATION_INTERVAL) {
      // More than 24h since last notification
      return true;
    }

    // Less than 24h, skip notification
    console.log(
      `⏭️  Skipping ${environment} no-alert notification (last sent ${(timeSinceLastNotification / (60 * 60 * 1000)).toFixed(1)}h ago)`,
    );
    return false;
  } catch (error) {
    console.error(`Error checking state for ${environment}:`, error.message);
    // On error, send the notification to be safe
    return true;
  }
};

/**
 * Update the state with the current timestamp
 */
const updateNoAlertNotificationState = (environment) => {
  try {
    const state = {
      lastNotificationTime: Date.now(),
    };
    updateState(environment, state);
  } catch (error) {
    console.error(`Error updating state for ${environment}:`, error.message);
  }
};

const checkSystemStatus = async () => {
  try {
    console.log("\ud83d\ude80 Starting system status check...");

    const startTime = Date.now();
    const monitors = await fetchAllMonitors();
    const fetchTime = ((Date.now() - startTime) / 1000).toFixed(1);

    console.log(
      `\ud83d\udcca Successfully fetched ${monitors.length} monitors`,
    );

    const categorized = categorizeMonitors(monitors);

    console.log("\n\ud83d\udcc8 Environment Summary:");
    console.log(`  Production: ${categorized.production.length} monitors`);
    console.log(`  Staging: ${categorized.staging.length} monitors`);

    // Production status (sent to production webhook)
    const prodStatus = createEnvironmentStatusMessage(
      categorized.production,
      "production",
      true,
    );

    // Check if we should send notification for production
    const hasProductionAlerts = prodStatus.downMonitors.length > 0;
    let shouldSendProdNotification = true;

    if (!hasProductionAlerts) {
      // No alerts - check if we sent a "no alerts" notification recently
      shouldSendProdNotification = shouldSendNoAlertNotification("production");
    }

    if (shouldSendProdNotification) {
      console.log(`📤 Sending PRODUCTION notification (${hasProductionAlerts ? prodStatus.downMonitors.length + ' alerts' : 'all clear'})`);
      await sendSlackAlert(SLACK_WEBHOOK_URL_PRODUCTION, prodStatus.message);

      if (hasProductionAlerts) {
        // Send detailed alert messages
        const downMessages = createDownMonitorsMessage(prodStatus.downMonitors);
        for (const downMsg of downMessages) {
          if (downMsg) {
            await sendSlackAlert(SLACK_WEBHOOK_URL_PRODUCTION, downMsg);
          }
        }
      } else {
        // Update state for "no alerts" notification
        updateNoAlertNotificationState("production");
      }
    }

    // Staging status (sent to staging webhook)
    const stagingStatus = createEnvironmentStatusMessage(
      categorized.staging,
      "staging",
      true,
    );

    // Check if we should send notification for staging
    const hasStagingAlerts = stagingStatus.downMonitors.length > 0;
    let shouldSendStagingNotification = true;

    if (!hasStagingAlerts) {
      // No alerts - check if we sent a "no alerts" notification recently
      shouldSendStagingNotification = shouldSendNoAlertNotification("staging");
    }

    if (shouldSendStagingNotification) {
      console.log(`📤 Sending STAGING notification (${hasStagingAlerts ? stagingStatus.downMonitors.length + ' alerts' : 'all clear'})`);
      await sendSlackAlert(SLACK_WEBHOOK_URL_STAGING, stagingStatus.message);

      if (hasStagingAlerts) {
        // Send detailed alert messages
        const downMessages = createDownMonitorsMessage(
          stagingStatus.downMonitors,
        );
        for (const downMsg of downMessages) {
          if (downMsg) {
            await sendSlackAlert(SLACK_WEBHOOK_URL_STAGING, downMsg);
          }
        }
      } else {
        // Update state for "no alerts" notification
        updateNoAlertNotificationState("staging");
      }
    }

    const totalTime = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(`\n\u2705 Status check completed in ${totalTime}s`);
    console.log(`   - Fetch time: ${fetchTime}s`);
    console.log(`   - Processing time: ${(totalTime - fetchTime).toFixed(1)}s`);
  } catch (error) {
    console.error("\u274c Error in status check:", error);

    // Send error notification to production channel
    await sendSlackAlert(
      SLACK_WEBHOOK_URL_PRODUCTION,
      `:x: *Monitor System Error*\nFailed to check system status: ${error.message}`,
    );
  }
};

// Run if called directly
if (require.main === module) {
  checkSystemStatus();
}

module.exports = { checkSystemStatus };
