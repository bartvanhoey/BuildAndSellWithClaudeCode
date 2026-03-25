import {
  schedules_exports
} from "../../../../../../../chunk-7X6IODCK.mjs";
import "../../../../../../../chunk-K6MMSPHX.mjs";
import {
  __name,
  init_esm
} from "../../../../../../../chunk-NVBOB5QU.mjs";

// src/trigger/dental-leads/find-dental-leads.ts
init_esm();
var NPPES_API = "https://npiregistry.cms.hhs.gov/api/";
var US_STATES = [
  "AL",
  "AK",
  "AZ",
  "AR",
  "CA",
  "CO",
  "CT",
  "DE",
  "FL",
  "GA",
  "HI",
  "ID",
  "IL",
  "IN",
  "IA",
  "KS",
  "KY",
  "LA",
  "ME",
  "MD",
  "MA",
  "MI",
  "MN",
  "MS",
  "MO",
  "MT",
  "NE",
  "NV",
  "NH",
  "NJ",
  "NM",
  "NY",
  "NC",
  "ND",
  "OH",
  "OK",
  "OR",
  "PA",
  "RI",
  "SC",
  "SD",
  "TN",
  "TX",
  "UT",
  "VT",
  "VA",
  "WA",
  "WV",
  "WI",
  "WY"
];
async function fetchDentistsFromNppes(state, skip = 0) {
  const params = new URLSearchParams({
    version: "2.1",
    enumeration_type: "NPI-2",
    taxonomy_description: "Dentist",
    state,
    limit: "200",
    skip: skip.toString()
  });
  const response = await fetch(`${NPPES_API}?${params}`);
  if (!response.ok) {
    throw new Error(`NPPES API error: ${response.status} ${response.statusText}`);
  }
  const data = await response.json();
  return data.results ?? [];
}
__name(fetchDentistsFromNppes, "fetchDentistsFromNppes");
async function checkHasWebsite(practiceName, city, state) {
  const query = encodeURIComponent(`"${practiceName}" dentist ${city} ${state} site`);
  const url = `https://html.duckduckgo.com/html/?q=${query}`;
  try {
    const response = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; DentalLeadsBot/1.0)",
        "Accept": "text/html"
      },
      signal: AbortSignal.timeout(8e3)
    });
    if (!response.ok) return false;
    const html = await response.text();
    const directoryDomains = [
      "yelp.com",
      "facebook.com",
      "healthgrades.com",
      "zocdoc.com",
      "vitals.com",
      "1-800-dentist.com",
      "yellowpages.com",
      "mapquest.com",
      "google.com",
      "bing.com",
      "duckduckgo.com",
      "findadentist.ada.org",
      "linkedin.com",
      "bbb.org",
      "angieslist.com",
      "nextdoor.com"
    ];
    const urlMatches = html.matchAll(/result__url[^>]*>([^<]+)</g);
    const resultUrls = [];
    for (const match of urlMatches) {
      resultUrls.push(match[1].trim().toLowerCase());
    }
    const hrefMatches = html.matchAll(/href="([^"]+)"[^>]*class="result__a"/g);
    for (const match of hrefMatches) {
      resultUrls.push(match[1].toLowerCase());
    }
    for (const url2 of resultUrls) {
      const isDirectory = directoryDomains.some((d) => url2.includes(d));
      if (!isDirectory && url2.length > 5) {
        return true;
      }
    }
    return false;
  } catch {
    return false;
  }
}
__name(checkHasWebsite, "checkHasWebsite");
async function createClickUpTask(practiceName, address, phone, npi, listId, apiToken) {
  const description = [
    `**NPI:** ${npi}`,
    `**Address:** ${address}`,
    `**Phone:** ${phone || "N/A"}`,
    "",
    "_No website detected — potential web design lead._"
  ].join("\n");
  const body = {
    name: practiceName,
    description,
    status: "to do",
    priority: 3,
    tags: ["dental-lead", "no-website"]
  };
  const response = await fetch(`https://api.clickup.com/api/v2/list/${listId}/task`, {
    method: "POST",
    headers: {
      Authorization: apiToken,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`ClickUp API error: ${response.status} — ${text}`);
  }
}
__name(createClickUpTask, "createClickUpTask");
var findDentalLeads = schedules_exports.task({
  id: "find-dental-leads",
  // Every Monday at 8am UTC
  cron: "0 8 * * 1",
  maxDuration: 600,
  run: /* @__PURE__ */ __name(async (payload) => {
    const clickupToken = process.env.CLICK_UP_API_TOKEN;
    if (!clickupToken) throw new Error("CLICK_UP_API_TOKEN is not set");
    const clickupListId = process.env.CLICKUP_DENTAL_LIST_ID;
    if (!clickupListId) throw new Error("CLICKUP_DENTAL_LIST_ID is not set");
    const weekNumber = Math.floor(payload.timestamp.getTime() / (7 * 24 * 60 * 60 * 1e3));
    const stateIndex = weekNumber * 2 % US_STATES.length;
    const statesToProcess = US_STATES.slice(stateIndex, stateIndex + 2);
    console.log(`Processing states: ${statesToProcess.join(", ")}`);
    let totalLeads = 0;
    let totalChecked = 0;
    for (const state of statesToProcess) {
      console.log(`Fetching dentists in ${state}...`);
      let skip = 0;
      let stateDentists = [];
      for (let page = 0; page < 3; page++) {
        const batch = await fetchDentistsFromNppes(state, skip);
        if (batch.length === 0) break;
        stateDentists = stateDentists.concat(batch);
        skip += 200;
        if (batch.length < 200) break;
      }
      console.log(`Found ${stateDentists.length} dentists in ${state}`);
      for (const dentist of stateDentists) {
        const practiceName = dentist.basic.organization_name ?? [dentist.basic.name_prefix, dentist.basic.first_name, dentist.basic.last_name].filter(Boolean).join(" ");
        if (!practiceName) continue;
        const practiceAddress = dentist.addresses.find(
          (a) => a.address_purpose === "LOCATION"
        ) ?? dentist.addresses[0];
        if (!practiceAddress) continue;
        const addressStr = [
          practiceAddress.address_1,
          practiceAddress.address_2,
          `${practiceAddress.city}, ${practiceAddress.state} ${practiceAddress.postal_code}`
        ].filter(Boolean).join(", ");
        const phone = practiceAddress.telephone_number ?? "";
        totalChecked++;
        const hasWebsite = await checkHasWebsite(
          practiceName,
          practiceAddress.city,
          practiceAddress.state
        );
        if (!hasWebsite) {
          console.log(`No website found for: ${practiceName} (${practiceAddress.city}, ${state})`);
          await createClickUpTask(
            practiceName,
            addressStr,
            phone,
            dentist.number,
            clickupListId,
            clickupToken
          );
          totalLeads++;
          await new Promise((resolve) => setTimeout(resolve, 1500));
        } else {
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
      }
    }
    console.log(`Done. Checked ${totalChecked} practices, found ${totalLeads} leads with no website.`);
    return {
      statesProcessed: statesToProcess,
      totalChecked,
      totalLeads
    };
  }, "run")
});
export {
  findDentalLeads
};
//# sourceMappingURL=find-dental-leads.mjs.map
