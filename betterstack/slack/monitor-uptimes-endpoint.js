require("dotenv").config({ path: __dirname + "/.env" });

const SLACK_WEBHOOK_URL_PRODUCTION = process.env.SLACK_WEBHOOK_URL_PRODUCTION; //#Alerting-Health-Check-Status
const SLACK_WEBHOOK_URL_STAGING = process.env.SLACK_WEBHOOK_URL_STAGING; //#alerting-health-check-staging-status

const BETTERSTACK_API_TOKEN = process.env.BETTERSTACK_API_TOKEN;
const BETTERSTACK_API_URL = "https://uptime.betterstack.com/api/v2/monitors";

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
    production: [],
    staging: [],
    explorerPreprod: [],
  };

  monitors.forEach((monitor) => {
    const url = monitor.attributes.url.toLowerCase();
    const name =
      monitor.attributes.pronounceable_name || monitor.attributes.url;

    // Explorer preprod: explorer-api.zobula.xyz/health
    if (url.includes("explorer-api.zobula.xyz/health")) {
      categories.explorerPreprod.push(monitor);
    }
    // Production: api.mobula.io (including explorer-api.mobula.io)
    else if (url.includes("api.mobula.io")) {
      categories.production.push(monitor);
    }
    // Staging: api.zobula.xyz but NOT explorer-api.zobula.xyz
    else if (
      url.includes("api.zobula.xyz") &&
      !url.includes("explorer-api.zobula.xyz")
    ) {
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
    console.log(
      `  Explorer Preprod: ${categorized.explorerPreprod.length} monitors`,
    );

    // Production status (sent to production webhook)
    const prodStatus = createEnvironmentStatusMessage(
      categorized.production,
      "production",
      true,
    );
    await sendSlackAlert(SLACK_WEBHOOK_URL_PRODUCTION, prodStatus.message);

    if (prodStatus.downMonitors.length > 0) {
      const downMessages = createDownMonitorsMessage(prodStatus.downMonitors);
      for (const downMsg of downMessages) {
        if (downMsg) {
          await sendSlackAlert(SLACK_WEBHOOK_URL_PRODUCTION, downMsg);
        }
      }
    }

    // Staging status (sent to staging webhook)
    const stagingStatus = createEnvironmentStatusMessage(
      categorized.staging,
      "staging",
      true,
    );
    await sendSlackAlert(SLACK_WEBHOOK_URL_STAGING, stagingStatus.message);

    if (stagingStatus.downMonitors.length > 0) {
      const downMessages = createDownMonitorsMessage(
        stagingStatus.downMonitors,
      );
      for (const downMsg of downMessages) {
        if (downMsg) {
          await sendSlackAlert(SLACK_WEBHOOK_URL_STAGING, downMsg);
        }
      }
    }

    // Explorer preprod status (sent to staging webhook)
    const explorerStatus = createEnvironmentStatusMessage(
      categorized.explorerPreprod,
      "explorer-preprod",
      true,
    );
    await sendSlackAlert(SLACK_WEBHOOK_URL_STAGING, explorerStatus.message);

    if (explorerStatus.downMonitors.length > 0) {
      const downMessages = createDownMonitorsMessage(
        explorerStatus.downMonitors,
      );
      for (const downMsg of downMessages) {
        if (downMsg) {
          await sendSlackAlert(SLACK_WEBHOOK_URL_STAGING, downMsg);
        }
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
