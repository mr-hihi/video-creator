/**
 * Flow Kit — Chrome Extension Background Service Worker
 *
 * Connects to local Python agent via WebSocket (agent runs WS server).
 * Mints reCAPTCHA and runs Flow's batchexecute RPCs inside the Flow tab.
 *
 * Flow moved to flow.google.com in September 2026 and stopped minting the
 * `Bearer ya29.…` the old REST host needed. The current path is `batch_rpc`:
 * the agent builds an `f.req` envelope, this worker mints a captcha for it and
 * runs the POST in the page's MAIN world, where the `at` CSRF token lives.
 * The bearer capture below is the pre-migration path.
 */

importScripts('agent_port.js');

let agentPort = DEFAULT_AGENT_PORT;
// NOTE: This is a browser-restricted public API key — safe to ship in extension bundles.
const API_KEY = 'AIzaSyBtrm0o5ab1c-Ec8ZuLcGt3oJAA5VWt3pY';

// labs.google/fx/tools/flow still resolves but redirects here, so in practice a
// signed-in tab is only ever flow.google.com/*. The legacy patterns stay for an
// old pinned tab. Every tab lookup in this file goes through this list.
const flowUrls = [
  'https://flow.google.com/*',
  'https://labs.google/fx/tools/flow*',
  'https://labs.google/fx/*/tools/flow*',
];
const FLOW_TAB_URL = 'https://flow.google.com/';

// ─── Temporary Netlog Recorder (docs/CAPTURE.md) ───────────
const NETLOG_HOSTS = ['https://flow.google.com/_/*'];
const netlogPending = new Map();

chrome.webRequest.onBeforeRequest.addListener(
  (d) => {
    let body = null;
    if (d.requestBody?.raw?.length) {
      body = new TextDecoder().decode(new Uint8Array(d.requestBody.raw[0].bytes));
    } else if (d.requestBody?.formData) {
      body = JSON.stringify(d.requestBody.formData);
    }
    netlogPending.set(d.requestId, { ts: new Date().toISOString(), url: d.url, method: d.method, body });
  },
  { urls: NETLOG_HOSTS },
  ['requestBody']
);

chrome.webRequest.onCompleted.addListener(
  (d) => {
    const rec = netlogPending.get(d.requestId);
    if (!rec) return;
    netlogPending.delete(d.requestId);
    sendToAgent({ type: 'netlog', ...rec, statusCode: d.statusCode });
  },
  { urls: NETLOG_HOSTS }
);

let ws = null;
let flowKey = null;
let state = 'off'; // off | idle | running
let manualDisconnect = false;
let metrics = {
  tokenCapturedAt: null,
  requestCount: 0,   // captcha-consuming requests only (gen image/video/upscale)
  successCount: 0,
  failedCount: 0,
  lastError: null,
};

// ─── Request Log ────────────────────────────────────────────

let requestLog = [];

function addRequestLog(entry) {
  requestLog.unshift(entry);
  if (requestLog.length > 100) requestLog.pop();
  broadcastRequestLog();
}

function updateRequestLog(id, updates) {
  const entry = requestLog.find((e) => e.id === id);
  if (entry) Object.assign(entry, updates);
  broadcastRequestLog();
}

function broadcastRequestLog() {
  chrome.runtime.sendMessage({ type: 'REQUEST_LOG_UPDATE', log: requestLog }).catch(() => {});
}

// ─── Startup ────────────────────────────────────────────────

let initializationPromise = null;

chrome.runtime.onInstalled.addListener(() => {
  void ensureInitialized();
});
chrome.runtime.onStartup.addListener(() => {
  void ensureInitialized();
});
chrome.alarms.onAlarm.addListener(async (alarm) => {
  await ensureInitialized();
  if (alarm.name === 'reconnect') connectToAgent();
  if (alarm.name === 'keepAlive') keepAlive();
  if (alarm.name === 'token-refresh') {
    // Passive maintenance must never create browser tabs. If the user has no
    // Flow tab open, wait for an explicit action or an actual RPC to open one.
    await captureTokenFromFlowTab({ createIfMissing: false });
  }
});

function ensureInitialized() {
  if (!initializationPromise) {
    initializationPromise = initialize().catch((error) => {
      initializationPromise = null;
      console.error('[FlowAgent] Initialization failed', error);
      throw error;
    });
  }
  return initializationPromise;
}

async function initialize() {
  const data = await chrome.storage.local.get(['flowKey', 'metrics', AGENT_PORT_KEY]);
  agentPort = toAgentPort(data[AGENT_PORT_KEY]);
  if (data.flowKey) flowKey = data.flowKey;
  if (data.metrics) Object.assign(metrics, data.metrics);
  connectToAgent();
  chrome.alarms.create('keepAlive', { periodInMinutes: 0.4 });
}

// MV3 workers can be suspended and restarted without onStartup firing.
// Rehydrate the persisted Flow key on every worker start.
void ensureInitialized();

chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local' || !changes[AGENT_PORT_KEY]) return;
  agentPort = toAgentPort(changes[AGENT_PORT_KEY].newValue);
  if (ws) {
    ws.close();
    return;
  }
  connectToAgent();
});

// ─── Token Capture ──────────────────────────────────────────

chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    if (!details?.requestHeaders?.length) return;
    const authHeader = details.requestHeaders.find(
      (h) => h.name?.toLowerCase() === 'authorization',
    );
    const value = authHeader?.value || '';
    if (!value.startsWith('Bearer ya29.')) return;

    const token = value.replace(/^Bearer\s+/i, '').trim();
    if (!token) return;

    // Always update — even if same token string, refresh the timestamp
    flowKey = token;
    metrics.tokenCapturedAt = Date.now();
    chrome.storage.local.set({ flowKey, metrics });
    console.log('[FlowAgent] Bearer token captured');
  },
  { urls: ['https://aisandbox-pa.googleapis.com/*', 'https://labs.google/*'] },
  ['requestHeaders', 'extraHeaders'],
);

let _openingFlowTab = false;

async function captureTokenFromFlowTab({ createIfMissing = false } = {}) {
  let tabs = await chrome.tabs.query({ url: flowUrls });
  if (!tabs.length) {
    if (!createIfMissing) {
      console.log('[FlowAgent] No Flow tab found — passive refresh skipped');
      return { skipped: 'NO_FLOW_TAB' };
    }
    if (_openingFlowTab) {
      console.log('[FlowAgent] Flow tab already opening, skipping');
      return;
    }
    _openingFlowTab = true;
    try {
      console.log('[FlowAgent] No Flow tab found — opening one for explicit refresh');
      const opened = await chrome.tabs.create({ url: FLOW_TAB_URL, active: false });
      await sleep(3000);
      const target = opened?.id ? await chrome.tabs.get(opened.id).catch(() => null) : null;
      if (!target) {
        console.log('[FlowAgent] Flow tab not ready yet after open');
        return;
      }
      await chrome.scripting.executeScript({
        target: { tabId: target.id },
        files: ['content.js'],
      });
      console.log('[FlowAgent] Token refresh triggered on newly opened Flow tab');
    } catch (e) {
      console.error('[FlowAgent] Token refresh failed after opening tab:', e);
    } finally {
      _openingFlowTab = false;
    }
    return;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId: tabs[0].id },
      files: ['content.js'],
    });
    console.log('[FlowAgent] Token refresh triggered on Flow tab');
  } catch (e) {
    console.error('[FlowAgent] Token refresh failed:', e);
  }
}

// ─── WebSocket to Agent ─────────────────────────────────────

function connectToAgent() {
  if (manualDisconnect) return;
  if (ws?.readyState === WebSocket.CONNECTING) return;
  if (ws?.readyState === WebSocket.OPEN) return;

  try {
    ws = new WebSocket(buildAgentWsUrl(agentPort));
  } catch (e) {
    console.error('[FlowAgent] WS connect error:', e);
    scheduleReconnect();
    return;
  }

  ws.onopen = () => {
    console.log('[FlowAgent] Connected to agent');
    chrome.alarms.clear('reconnect');
    setState('idle');

    // Token refresh alarm — 45 min gives buffer before ~60 min expiry
    chrome.alarms.create('token-refresh', { periodInMinutes: 45 });

    // Send current state + resend token if we have one
    ws.send(JSON.stringify({
      type: 'extension_ready',
      flowKeyPresent: !!flowKey,
      extensionVersion: chrome.runtime.getManifest().version,
      flowUrlSupported: chrome.runtime.getManifest().host_permissions?.includes('https://flow.google.com/*') === true,
      tokenAge: flowKey && metrics.tokenCapturedAt ? Date.now() - metrics.tokenCapturedAt : null,
    }));
  };

  ws.onmessage = async ({ data }) => {
    try {
      const msg = JSON.parse(data);

      if (msg.method === 'batch_rpc') {
        await handleBatchRpc(msg);
      } else if (msg.type === 'open_flow_tab') {
        await openFlowTab();
      } else if (msg.type === 'pong') {
        // keepalive response
      }
    } catch (e) {
      console.error('[FlowAgent] Message error:', e);
    }
  };

  ws.onclose = () => {
    setState('off');
    chrome.alarms.clear('token-refresh');
    if (!manualDisconnect) scheduleReconnect();
  };

  ws.onerror = (e) => {
    console.error('[FlowAgent] WS error:', e);
    metrics.lastError = 'WS_ERROR';
    chrome.storage.local.set({ metrics });
  };
}

function scheduleReconnect() {
  chrome.alarms.create('reconnect', { delayInMinutes: 0.083 }); // ~5s
}

function keepAlive() {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ping' }));
  } else {
    connectToAgent();
  }
}

function sendToAgent(msg) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}

// ─── reCAPTCHA Solving ──────────────────────────────────────

async function requestCaptchaFromTab(tabId, requestId, pageAction) {
  try {
    return await chrome.tabs.sendMessage(tabId, {
      type: 'GET_CAPTCHA',
      requestId,
      pageAction,
    });
  } catch (error) {
    const msg = error?.message || '';
    const shouldInject =
      msg.includes('Receiving end does not exist') ||
      msg.includes('Could not establish connection');
    if (!shouldInject) throw error;

    // Inject content script and retry
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content.js'],
    });
    await sleep(200);
    return await chrome.tabs.sendMessage(tabId, {
      type: 'GET_CAPTCHA',
      requestId,
      pageAction,
    });
  }
}

/** Try to wake a discarded Flow tab so `sendMessage` can reach it.
 *  Chrome auto-discards backgrounded tabs to save memory; the tab still shows
 *  up in `chrome.tabs.query` but cross-context calls fail with "No current
 *  window" / "No tab with id". A reload re-hydrates it. */
async function reviveTabIfNeeded(tab) {
  if (!tab?.discarded) return tab;
  try {
    await chrome.tabs.reload(tab.id);
    await sleep(2500);
    return await chrome.tabs.get(tab.id);
  } catch {
    return null;
  }
}

function captchaFromTab(tabId, requestId, captchaAction) {
  return Promise.race([
    requestCaptchaFromTab(tabId, requestId, captchaAction),
    new Promise((_, rej) => setTimeout(() => rej(new Error('CAPTCHA_TIMEOUT')), 30000)),
  ]);
}

async function solveCaptcha(requestId, captchaAction) {
  let tabs = await chrome.tabs.query({ url: flowUrls });

  // No Flow tab at all — spawn one and let it settle. Keep the exact tab id:
  // a redirected or stale tab must not make us select some older candidate.
  if (!tabs.length) {
    let opened;
    try {
      opened = await chrome.tabs.create({ url: FLOW_TAB_URL, active: false });
      await sleep(3000);
    } catch (e) {
      return { error: e.message || 'NO_FLOW_TAB' };
    }
    const target = opened?.id ? await chrome.tabs.get(opened.id).catch(() => null) : null;
    if (!target) return { error: 'NO_FLOW_TAB' };
    tabs = [target];
  }

  // Try each Flow tab in turn. A tab that answers "no grecaptcha" is a tab
  // Try project tabs first (they have the full toolchain and recaptcha context loaded)
  tabs.sort((a, b) => ((b.url && b.url.includes('/project/')) ? 1 : 0) - ((a.url && a.url.includes('/project/')) ? 1 : 0));
  const errors = [];
  for (const candidate of tabs) {
    const tab = await reviveTabIfNeeded(candidate);
    if (!tab) continue;
    try {
      const resp = await captchaFromTab(tab.id, requestId, captchaAction);
      if (!resp?.token) {
        errors.push(resp?.error || 'NO_TOKEN');
        continue;
      }
      return resp;
    } catch (e) {
      const msg = e?.message || '';
      errors.push(msg);
      // Tab evaporated mid-call (window closed, discarded again, navigated
      // away). Move on to the next candidate rather than failing the job.
      if (
        msg.includes('No current window') ||
        msg.includes('No tab with id') ||
        msg.includes('Receiving end does not exist')
      ) {
        continue;
      }
      return { error: msg };
    }
  }

  // Every candidate failed — last-ditch, spawn a fresh temporary tab and
  // target THAT exact tab. Previously we re-queried all Flow tabs and picked
  // fresh[0], which could select the same stale tab again while leaking the
  // newly-created one on every retry.
  let recoveryTab = null;
  try {
    recoveryTab = await chrome.tabs.create({ url: FLOW_TAB_URL, active: false });
    await sleep(3000);
    const target = await chrome.tabs.get(recoveryTab.id);
    if (!target || target.discarded) return { error: 'NO_FLOW_TAB' };
    return await captchaFromTab(target.id, requestId, captchaAction);
  } catch (e) {
    return { error: e?.message || errors[0] || 'NO_FLOW_TAB' };
  } finally {
    // A recovery tab is disposable: there were already Flow tabs available
    // for the signed RPC. Do not let CAPTCHA retries accumulate root tabs.
    if (recoveryTab?.id) {
      try { await chrome.tabs.remove(recoveryTab.id); } catch { /* already gone */ }
    }
  }
}

// ─── Page-context RPC runner (the current path) ─────────────
//
// Flow's frontend signs its calls with cookies and a per-page `at` token, and
// every generate carries a single-use reCAPTCHA. None of that can be replayed
// from the service worker, so the request has to be issued by the Flow page
// itself: mint a fresh captcha through the grecaptcha bridge, then run the
// batchexecute POST in the page's MAIN world, where at / f.sid / bl live.

const CAPTCHA_SLOT = '__CAPTCHA__';
const MAX_RPC_TEXT = 32000000; // the project listing alone is past 17 MB

async function runBatchRpc(cmd) {
  const tabs = await chrome.tabs.query({ url: flowUrls });
  let candidate =
    tabs.find((t) => t.url && t.url.includes('/project/') && !t.discarded) ||
    tabs.find((t) => t.active && !t.discarded) ||
    tabs.find((t) => !t.discarded) ||
    tabs[0];
  if (!candidate) {
    // No Flow tab — open one and give the app a moment to boot, otherwise
    // WIZ_global_data is not on the page yet and `at` comes back empty. Keep
    // the exact created tab id so redirects/stale tabs cannot hijack recovery.
    let opened;
    try {
      opened = await chrome.tabs.create({ url: FLOW_TAB_URL, active: false });
      await sleep(5000);
      candidate = opened?.id ? await chrome.tabs.get(opened.id).catch(() => null) : null;
    } catch (e) {
      return { error: e?.message || 'NO_FLOW_TAB' };
    }
    if (!candidate) return { error: 'NO_FLOW_TAB' };
  }
  // Chrome discards backgrounded tabs; executeScript throws on a dead one.
  const tab = await reviveTabIfNeeded(candidate);
  if (!tab) return { error: 'FLOW_TAB_DISCARDED' };

  let freq = cmd.freq;
  if (cmd.captchaAction) {
    const solved = await captchaFromTab(tab.id, cmd.id, cmd.captchaAction);
    if (!solved?.token) return { error: `CAPTCHA_FAILED: ${solved?.error || 'no token'}` };
    freq = freq.split(CAPTCHA_SLOT).join(solved.token);
  }

  const [injected] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    world: 'MAIN',
    args: [cmd.rpcid, freq, MAX_RPC_TEXT, cmd.match || null],
    func: async (rpcid, freqStr, maxText, match) => {
      const wiz = globalThis.WIZ_global_data || {};
      const at = wiz.SNlM0e;
      const sid = wiz.FdrFJe;
      const bl = wiz.cfb2h;
      if (!at) return { error: 'NO_AT_TOKEN' };

      const reqid = Math.floor(Math.random() * 900000) + 100000;
      // Match Flow's own WIZ metadata. GEM_PIX_2 (Nano Banana Pro) rejects
      // image generation when source-path is missing even though Lite may not.
      const sourcePath = location.pathname || '/';
      const hl = (document.documentElement.lang || navigator.language || 'en').split('-')[0];
      const url = `/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=${encodeURIComponent(rpcid)}` +
        `&source-path=${encodeURIComponent(sourcePath)}` +
        `&bl=${encodeURIComponent(bl || '')}&f.sid=${encodeURIComponent(sid || '')}` +
        `&hl=${encodeURIComponent(hl)}&_reqid=${reqid}&rt=c`;
      const resp = await fetch(url, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'x-same-domain': '1',
        },
        body: new URLSearchParams({ 'f.req': freqStr, at }),
      });
      const text = await resp.text();
      // The project listing is tens of megabytes and all we ever want from it
      // is one entry. Cutting it down here keeps that payload inside the tab
      // instead of pushing it through the bridge on every poll.
      if (match) {
        const lowerText = text.toLowerCase();
        const lowerMatch = match.toLowerCase();
        const found = lowerText.indexOf(lowerMatch);
        if (found !== -1) {
          const start = Math.max(0, found - 400);
          const end = Math.min(text.length, found + 800);
          return {
            status: resp.status,
            matched: true,
            text: text.slice(start, end),
          };
        }
        return {
          status: resp.status,
          matched: false,
          text: '',
        };
      }
      return { status: resp.status, text: text.slice(0, maxText) };
    },
  });

  return injected?.result || { error: 'NO_INJECTION_RESULT' };
}

async function handleBatchRpc(msg) {
  const { id, params } = msg;
  const { rpcid, freq, captchaAction, match } = params || {};
  if (!rpcid || !freq) {
    sendToAgent({ id, status: 400, error: 'INVALID_BATCH_RPC' });
    return;
  }

  setState('running');
  const hasCaptcha = !!captchaAction;
  if (hasCaptcha) metrics.requestCount++;
  // Polls and listing lookups run constantly; only the generates are worth
  // a row in the log the popup shows.
  const visible = hasCaptcha;
  const _RPC_LABELS = {
    ogiZ0b: 'Gen Image', eb1hJf: 'Gen Video', YhhmEf: 'Gen Video (text)',
    nprQif: 'Gen Video (chain)', MZZa6b: 'Gen Video (refs)',
    maseQ: 'Upload Image', SPrCad: 'Upscale Image',
    jHPbke: 'Create Project', jwpduf: 'Poll Operation',
    Zzl0ze: 'Project Media', as29s: 'Get Media',
  };
  const logType = _RPC_LABELS[rpcid] || `RPC:${rpcid}`;
  if (visible) {
    addRequestLog({
      id, type: logType, time: new Date().toISOString(),
      status: 'processing', error: null, outputUrl: null, url: rpcid,
      payloadSummary: freq.slice(0, 200),
    });
  }

  try {
    const out = await runBatchRpc({ id, rpcid, freq, captchaAction, match });
    if (out.error) {
      if (hasCaptcha) { metrics.failedCount++; metrics.lastError = out.error; }
      if (visible) updateRequestLog(id, { status: 'failed', error: out.error });
      sendToAgent({ id, status: 502, error: out.error });
    } else {
      if (hasCaptcha) { metrics.successCount++; metrics.lastError = null; }
      if (visible) {
        updateRequestLog(id, {
          status: 'success', httpStatus: out.status,
          responseSummary: (out.text || '').slice(0, 300),
        });
      }
      sendToAgent({ id, status: out.status, data: out.text });
    }
  } catch (e) {
    const err = e?.message || 'BATCH_RPC_FAILED';
    if (hasCaptcha) { metrics.failedCount++; metrics.lastError = err; }
    if (visible) updateRequestLog(id, { status: 'failed', error: err });
    sendToAgent({ id, status: 500, error: err });
  }

  chrome.storage.local.set({ metrics });
  setState('idle');
}

// ─── State & Popup ──────────────────────────────────────────

function setState(newState) {
  state = newState;
  const badges = { idle: '●', running: '▶', off: '○' };
  const colors = { idle: '#22c55e', running: '#f59e0b', off: '#6b7280' };
  chrome.action.setBadgeText({ text: badges[state] || '' });
  chrome.action.setBadgeBackgroundColor({ color: colors[state] || '#000' });
  broadcastStatus();
}

function broadcastStatus() {
  chrome.runtime.sendMessage({ type: 'STATUS_PUSH' }).catch(() => {});
}

chrome.runtime.onMessage.addListener((msg, _, reply) => {
  if (msg.type === 'STATUS') {
    reply({
      connected: ws?.readyState === WebSocket.OPEN,
      agentConnected: ws?.readyState === WebSocket.OPEN,
      flowKeyPresent: !!flowKey,
      manualDisconnect,
      tokenAge: metrics.tokenCapturedAt ? Date.now() - metrics.tokenCapturedAt : null,
      metrics: {
        requestCount: metrics.requestCount,
        successCount: metrics.successCount,
        failedCount: metrics.failedCount,
        lastError: metrics.lastError,
      },
      state,
    });
  }

  if (msg.type === 'DISCONNECT') {
    manualDisconnect = true;
    if (ws) ws.close();
    reply({ ok: true });
    return true;
  }

  if (msg.type === 'RECONNECT') {
    manualDisconnect = false;
    connectToAgent();
    reply({ ok: true });
    return true;
  }

  if (msg.type === 'REQUEST_LOG') {
    reply({ log: requestLog });
    return true;
  }

  if (msg.type === 'OPEN_FLOW_TAB') {
    openFlowTab().then(reply);
    return true;
  }

  if (msg.type === 'REFRESH_TOKEN') {
    captureTokenFromFlowTab({ createIfMissing: true })
      .then(() => reply({ ok: true }))
      .catch((e) => reply({ error: e.message }));
    return true;
  }

  if (msg.type === 'TEST_CAPTCHA') {
    solveCaptcha(`test-${Date.now()}`, msg.pageAction || 'IMAGE_GENERATION')
      .then((r) => reply(r))
      .catch((e) => reply({ error: e.message }));
    return true;
  }


  if (msg.type === 'TRPC_MEDIA_URLS') {
    handleTrpcMediaUrls(msg.trpcUrl, msg.body);
    reply({ ok: true });
    return true;
  }

  return true;
});

// ─── TRPC Media URL Extractor ──────────────────────────────

function handleTrpcMediaUrls(trpcUrl, bodyText) {
  try {
    // Extract all fresh GCS signed URLs
    const urlRegex = /https:\/\/storage\.googleapis\.com\/ai-sandbox-videofx\/(?:image|video)\/[0-9a-f-]{36}\?[^"'\s]+/g;
    const matches = bodyText.match(urlRegex) || [];
    if (!matches.length) return;

    // Deduplicate and parse
    const urlMap = {};
    for (const rawUrl of matches) {
      // Unescape JSON-escaped URLs
      const url = rawUrl.replace(/\\u0026/g, '&').replace(/\\/g, '');
      const mediaMatch = url.match(/\/(image|video)\/([0-9a-f-]{36})\?/);
      if (mediaMatch) {
        const [, mediaType, mediaId] = mediaMatch;
        // Keep last occurrence (freshest)
        urlMap[mediaId] = { mediaType, url, mediaId };
      }
    }

    const entries = Object.values(urlMap);
    if (!entries.length) return;

    console.log(`[FlowAgent] Captured ${entries.length} fresh media URLs from TRPC`);
    // URL refresh is silent — don't show in request log

    // Forward to agent for DB update
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'media_urls_refresh',
        urls: entries,
      }));
    }
  } catch (e) {
    console.error('[FlowAgent] Failed to extract TRPC media URLs:', e);
  }
}

async function openFlowTab() {
  try {
    const tabs = await chrome.tabs.query({ url: flowUrls });
    if (!tabs.length) {
      const created = await chrome.tabs.create({ url: FLOW_TAB_URL });
      return { ok: true, tabId: created.id };
    }
    const [tab] = tabs;
    await chrome.tabs.update(tab.id, { active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
    return { ok: true, tabId: tab.id };
  } catch (e) {
    return { error: e.message };
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ─── Human-like Telemetry ──────────────────────────────────
// Periodically send tracking events to Google's analytics endpoints
// to mimic normal browser behavior.

const _UA = navigator.userAgent;
let _telemetrySessionId = `;${Date.now()}`;

function _rand(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }

function _buildBatchLogPayload() {
  const events = [];
  const types = ['FLOW_IMAGE_LATENCY', 'FLOW_VIDEO_LATENCY'];
  const count = _rand(1, 3);
  for (let i = 0; i < count; i++) {
    events.push({
      event: types[_rand(0, types.length - 1)],
      eventProperties: [
        { key: 'CURRENT_TIME_MS', doubleValue: Date.now() },
        { key: 'DURATION_MS', doubleValue: _rand(150, 800) },
        { key: 'USER_AGENT', stringValue: _UA },
        { key: 'IS_DESKTOP', booleanValue: true },
      ],
      eventMetadata: { sessionId: _telemetrySessionId },
      eventTime: new Date().toISOString(),
    });
  }
  return { appEvents: events };
}

function _buildFrontendEventsPayload() {
  const eventTypes = [
    'FLOW_IMAGE_LATENCY', 'FLOW_VIDEO_LATENCY', 'GRID_SCROLL_DEPTH',
    'FLOW_PROJECT_OPEN', 'FLOW_SCENE_VIEW',
  ];
  const count = _rand(1, 4);
  const events = [];
  for (let i = 0; i < count; i++) {
    const et = eventTypes[_rand(0, eventTypes.length - 1)];
    const params = {
      USER_AGENT: { '@type': 'type.googleapis.com/google.protobuf.StringValue', value: _UA },
      IS_DESKTOP: { '@type': 'type.googleapis.com/google.protobuf.StringValue', value: 'true' },
    };
    if (et.includes('LATENCY')) {
      params.CURRENT_TIME_MS = { '@type': 'type.googleapis.com/google.protobuf.StringValue', value: String(Date.now()) };
      params.DURATION_MS = { '@type': 'type.googleapis.com/google.protobuf.StringValue', value: String(_rand(100, 600)) };
    }
    if (et === 'GRID_SCROLL_DEPTH') {
      params.MEDIA_GENERATION_PAYGATE_TIER = { '@type': 'type.googleapis.com/google.protobuf.StringValue', value: 'PAYGATE_TIER_TWO' };
    }
    events.push({
      eventType: et,
      metadata: {
        sessionId: _telemetrySessionId,
        createTime: new Date().toISOString(),
        additionalParams: params,
      },
    });
  }
  return { events };
}

async function sendTelemetry() {
  // Legacy-path camouflage: these endpoints want the bearer Flow no longer
  // mints, so on the batch path there is no flowKey and this is a no-op.
  if (!flowKey || state === 'off') return;

  const headers = {
    'Content-Type': 'text/plain;charset=UTF-8',
    'authorization': `Bearer ${flowKey}`,
  };

  // Telemetry is silent — don't show in request log
  try {
    if (Math.random() < 0.5) {
      await fetch(`https://aisandbox-pa.googleapis.com/v1:batchLog`, {
        method: 'POST', headers, credentials: 'include',
        body: JSON.stringify(_buildBatchLogPayload()),
      });
    } else {
      await fetch(`https://aisandbox-pa.googleapis.com/v1/flow:batchLogFrontendEvents`, {
        method: 'POST', headers, credentials: 'include',
        body: JSON.stringify(_buildFrontendEventsPayload()),
      });
    }
  } catch {}
}

// Send telemetry at random intervals (45-120s) to look organic
function scheduleTelemetry() {
  const delay = _rand(45, 120) * 1000;
  setTimeout(async () => {
    await sendTelemetry();
    scheduleTelemetry(); // reschedule with new random interval
  }, delay);
}

// Refresh session ID every ~30min like a real user
setInterval(() => { _telemetrySessionId = `;${Date.now()}`; }, _rand(25, 35) * 60 * 1000);

scheduleTelemetry();

console.log('[FlowAgent] Extension loaded');
