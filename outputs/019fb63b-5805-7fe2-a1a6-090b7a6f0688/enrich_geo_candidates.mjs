import fs from "node:fs/promises";

const outputDir =
  "/Users/alankritghosh/JARVIS /jarvis_engineering/outputs/019fb63b-5805-7fe2-a1a6-090b7a6f0688";
const rawPath = `${outputDir}/geo_candidates_raw.json`;
const outputPath = `${outputDir}/geo_candidates_enriched.json`;

const existingRecipients = new Set(
  [
    "info@complydo.io",
    "founders@zeit-ai.com",
    "founders@alguna.io",
    "andrew@l2labs.ai",
    "ben@civtiq.com",
    "hiring@learndelta.ai",
    "careers@revion.inc",
    "info@eduvero.com",
    "brandon@getabacus.com",
    "hello@phase.law",
    "win@dedaluslabs.ai",
    "leandrew@posterchild.ai",
    "hello@ctgt.ai",
    "jobs@drswarm.com",
    "founders@agentmail.cc",
    "info@carohq.com",
    "luigi@manufact.com",
  ].map((email) => email.toLowerCase()),
);

const existingCompanies = new Set(
  [
    "Abacus",
    "AgentMail",
    "Alguna",
    "Caro",
    "ComplyDo",
    "CTGT",
    "Dedalus Labs",
    "Delta",
    "DrSwarm",
    "Eduvero",
    "Manufact",
    "Phaselaw",
    "PosterChild",
    "Revion",
    "Zeit AI",
  ].map((name) => name.toLowerCase()),
);

function decodeHtml(value) {
  return String(value || "")
    .replaceAll("&quot;", '"')
    .replaceAll("&#x27;", "'")
    .replaceAll("&#39;", "'")
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&nbsp;", " ")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)));
}

function stripHtml(value) {
  return decodeHtml(value)
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function extractDataPage(html) {
  const match = html.match(/\bdata-page="([^"]+)"/);
  if (!match) return null;
  try {
    return JSON.parse(decodeHtml(match[1]));
  } catch {
    return null;
  }
}

function normalizeEmail(value) {
  return String(value || "")
    .replace(/^mailto:/i, "")
    .split("?")[0]
    .trim()
    .toLowerCase()
    .replace(/[),.;:]+$/, "");
}

function extractEmails(html) {
  const decoded = decodeHtml(html);
  const found = new Set();
  for (const match of decoded.matchAll(/mailto:([^"'?#\s<>]+)/gi)) {
    found.add(normalizeEmail(match[1]));
  }
  for (const match of stripHtml(decoded).matchAll(
    /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,
  )) {
    found.add(normalizeEmail(match[0]));
  }
  return [...found].filter(
    (email) =>
      /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) &&
      !email.includes("example.") &&
      !email.endsWith("@sentry.io") &&
      !email.endsWith("@wixpress.com") &&
      !email.startsWith("noreply@") &&
      !email.startsWith("no-reply@"),
  );
}

function scoreEmail(email, founders = []) {
  const local = email.split("@")[0];
  const founderTokens = founders
    .flatMap((founder) => String(founder.full_name || founder.name || "").toLowerCase().split(/\W+/))
    .filter((token) => token.length >= 3);
  if (founderTokens.some((token) => local.includes(token))) return 100;
  if (/^(founder|founders|ceo|cto)$/.test(local)) return 95;
  if (/^(hello|team|contact|info)$/.test(local)) return 85;
  if (/^(jobs|careers|hiring|talent)$/.test(local)) return 75;
  if (/^(support|help|sales)$/.test(local)) return 45;
  if (/^(privacy|legal|security|press|billing|accounts|admin)$/.test(local)) return 10;
  return 60;
}

function uniqueContactLinks(html, baseUrl) {
  const links = [];
  for (const match of html.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)) {
    const href = decodeHtml(match[1]);
    const text = stripHtml(match[2]).toLowerCase();
    if (!/(contact|about|team|career|jobs|hiring)/i.test(`${href} ${text}`)) continue;
    try {
      const url = new URL(href, baseUrl);
      const base = new URL(baseUrl);
      if (!/^https?:$/.test(url.protocol) || url.origin !== base.origin) continue;
      if (!links.includes(url.href)) links.push(url.href);
    } catch {
      // Ignore malformed page links.
    }
  }
  return links.slice(0, 4);
}

async function fetchText(url, timeoutMs = 12000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      redirect: "follow",
      signal: controller.signal,
      headers: {
        "user-agent":
          "Mozilla/5.0 (compatible; IcarusProspectResearch/1.0; +https://www.ycombinator.com/)",
        accept: "text/html,application/xhtml+xml",
      },
    });
    const contentType = response.headers.get("content-type") || "";
    if (!response.ok || !contentType.includes("text/html")) {
      return { ok: false, url: response.url || url, html: "", status: response.status };
    }
    const html = (await response.text()).slice(0, 3_000_000);
    return { ok: true, url: response.url || url, html, status: response.status };
  } catch (error) {
    return { ok: false, url, html: "", status: 0, error: String(error) };
  } finally {
    clearTimeout(timer);
  }
}

async function mapLimit(items, concurrency, mapper) {
  const results = new Array(items.length);
  let index = 0;
  async function worker() {
    while (index < items.length) {
      const current = index++;
      results[current] = await mapper(items[current], current);
    }
  }
  await Promise.all(Array.from({ length: concurrency }, () => worker()));
  return results;
}

function cardHasLiveEngineeringJob(row) {
  const roles = (row.jobs || []).filter((job) => job.title && job.title !== "View job");
  if (!roles.length) return false;
  return roles.some((job) =>
    /(engineer|engineering|developer|technical|scientist|research|security|infrastructure|systems|robotics|ml|ai)/i.test(
      job.title,
    ),
  );
}

const raw = JSON.parse(await fs.readFile(rawPath, "utf8"));
const uniqueBySlug = new Map();
for (const row of raw) {
  if (!row.slug || !cardHasLiveEngineeringJob(row)) continue;
  const key = row.slug.toLowerCase();
  const prior = uniqueBySlug.get(key);
  if (!prior || (row.jobs || []).length > (prior.jobs || []).length) uniqueBySlug.set(key, row);
}

const candidates = [...uniqueBySlug.values()];
const enriched = await mapLimit(candidates, 6, async (row) => {
  const slug = row.slug.replace(/^\/companies\//, "");
  const ycUrl = `https://www.ycombinator.com/companies/${slug}`;
  const ycResponse = await fetchText(ycUrl);
  const page = ycResponse.ok ? extractDataPage(ycResponse.html) : null;
  const company = page?.props?.company || null;
  const founders = company?.founders || page?.props?.founders || [];
  const website = company?.website || "";
  const pagesChecked = [];
  const emailEvidence = [];

  if (website) {
    const home = await fetchText(website);
    if (home.ok) {
      pagesChecked.push(home.url);
      for (const email of extractEmails(home.html)) {
        emailEvidence.push({ email, source: home.url });
      }
      const contactLinks = uniqueContactLinks(home.html, home.url);
      for (const link of contactLinks) {
        const contact = await fetchText(link);
        if (!contact.ok) continue;
        pagesChecked.push(contact.url);
        for (const email of extractEmails(contact.html)) {
          emailEvidence.push({ email, source: contact.url });
        }
      }
    }
  }

  const dedupedEvidence = [];
  const seenEmails = new Set();
  for (const item of emailEvidence) {
    if (!seenEmails.has(item.email)) {
      seenEmails.add(item.email);
      dedupedEvidence.push(item);
    }
  }
  const rankedEmails = dedupedEvidence
    .map((item) => ({ ...item, score: scoreEmail(item.email, founders) }))
    .sort((a, b) => b.score - a.score || a.email.localeCompare(b.email));
  const preferred = rankedEmails.find((item) => item.score >= 60) || null;
  const name = company?.name || row.text?.split("\n")[0]?.replace(/\([^)]*\)$/, "") || slug;

  return {
    name,
    slug,
    discoveryGeography: row.geography,
    ycUrl,
    website,
    oneLiner: company?.one_liner || row.text?.split("\n")[1] || "",
    longDescription: company?.long_description || "",
    foundedYear: company?.year_founded || null,
    teamSize: company?.team_size || null,
    location: company?.location || "",
    city: company?.city || "",
    country: company?.country || "",
    companyLinkedIn: company?.linkedin_url || "",
    founders: founders.map((founder) => ({
      name: founder.full_name || founder.name || "",
      title: founder.title || founder.job_title || "Founder",
      linkedin: founder.linkedin_url || "",
      twitter: founder.twitter_url || "",
    })),
    roles: (row.jobs || [])
      .filter((job) => job.title && job.title !== "View job")
      .map((job) => ({ title: job.title, url: job.url })),
    preferredEmail: preferred?.email || "",
    emailSource: preferred?.source || "",
    publishedEmails: rankedEmails,
    pagesChecked,
    duplicateCompany: existingCompanies.has(name.toLowerCase()),
    duplicateRecipient: preferred ? existingRecipients.has(preferred.email) : false,
    ycPageVerified: Boolean(company),
  };
});

await fs.writeFile(outputPath, JSON.stringify(enriched, null, 2));
const summary = {
  rawRows: raw.length,
  uniqueLiveEngineeringCompanies: candidates.length,
  ycPagesVerified: enriched.filter((row) => row.ycPageVerified).length,
  publishedEmailFound: enriched.filter((row) => row.preferredEmail).length,
  newEmailReady: enriched.filter(
    (row) => row.preferredEmail && !row.duplicateCompany && !row.duplicateRecipient,
  ).length,
  outputPath,
};
console.log(JSON.stringify(summary, null, 2));
