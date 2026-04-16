/**
 * Dev-only mock API.
 *
 * When VITE_USE_MOCK_API=true, the axios instance in ./api.js installs this
 * adapter instead of making real network calls. The goal is to let the full
 * frontend be demoed / developed without the backend running — every page
 * the router can reach should receive a realistic fixture shaped exactly
 * like the FastAPI responses.
 *
 * This is intentionally NOT imported unless the env flag is on, so it is
 * tree-shaken out of production builds.
 */

const DELAY_MS = 250;

// ---------- Seed data ----------
const SEED_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'admin@invoice.local',
  full_name: 'Ada Admin',
  role: 'ADMIN',
  is_active: true,
  created_at: '2026-01-01T09:00:00Z',
};

const VENDORS = [
  'Acme Corp', 'Globex Industries', 'Initech', 'Umbrella Co',
  'Stark Industries', 'Wayne Enterprises', 'Wonka Ltd', 'Pied Piper',
];

const STATUSES = [
  'UPLOADED', 'PROCESSING', 'AUTO_APPROVED', 'REVIEW_REQUIRED',
  'APPROVED', 'REJECTED', 'POSTED', 'FAILED',
];

function rnd(seed) {
  // tiny deterministic PRNG so the demo list is stable between reloads
  let x = seed;
  return () => {
    x = (x * 9301 + 49297) % 233280;
    return x / 233280;
  };
}

function makeInvoice(i) {
  const r = rnd(i + 1);
  const vendor = VENDORS[Math.floor(r() * VENDORS.length)];
  const status = STATUSES[Math.floor(r() * STATUSES.length)];
  const total = Math.round(r() * 500000) / 100;
  const tax = Math.round(total * 0.08 * 100) / 100;
  const subtotal = Math.round((total - tax) * 100) / 100;
  const createdDaysAgo = Math.floor(r() * 30);
  const created = new Date(Date.now() - createdDaysAgo * 86400000).toISOString();
  return {
    id: `invoice-${String(i).padStart(4, '0')}`,
    original_filename: `invoice_${1000 + i}.pdf`,
    vendor_name: vendor,
    invoice_number: `INV-${2026}-${String(1000 + i)}`,
    invoice_date: created.slice(0, 10),
    currency: 'USD',
    subtotal,
    tax_amount: tax,
    total_amount: total,
    status,
    confidence_score: Math.round((0.6 + r() * 0.39) * 100) / 100,
    created_at: created,
    updated_at: created,
  };
}

const INVOICES = Array.from({ length: 48 }, (_, i) => makeInvoice(i));

function makeDetail(id) {
  const idx = Number(id.split('-').pop());
  const base = INVOICES[idx] || INVOICES[0];
  const champ = {
    vendor_name: base.vendor_name,
    invoice_number: base.invoice_number,
    invoice_date: base.invoice_date,
    currency: base.currency,
    subtotal: base.subtotal,
    tax_amount: base.tax_amount,
    total_amount: base.total_amount,
    purchase_order: `PO-${8000 + idx}`,
    items: [
      { description: 'Consulting services', quantity: 10, unit_price: 150, line_total: 1500 },
      { description: 'Software license', quantity: 1, unit_price: base.subtotal - 1500, line_total: base.subtotal - 1500 },
    ],
    confidence_scores: {
      vendor_name: 0.97, invoice_number: 0.95, total_amount: 0.98,
      subtotal: 0.94, tax_amount: 0.93,
    },
    raw: { engine: 'azure_di', model: 'prebuilt-invoice' },
  };
  // Challenger has a minor mismatch to exercise the compare UI
  const challenger = {
    ...champ,
    total_amount: base.status === 'REVIEW_REQUIRED'
      ? Math.round((base.total_amount + 5) * 100) / 100
      : base.total_amount,
    confidence_scores: {
      vendor_name: 0.88, invoice_number: 0.90, total_amount: 0.86,
      subtotal: 0.84, tax_amount: 0.82,
    },
    raw: { engine: 'paddle_ocr', line_count: 42 },
  };
  return {
    ...base,
    file_url: '#mock-file',
    champ_extraction: champ,
    challenger_extraction: challenger,
    validation: {
      decision: base.status === 'AUTO_APPROVED' ? 'AUTO_APPROVE'
        : base.status === 'REJECTED' ? 'REJECT' : 'REVIEW',
      mismatches: base.status === 'REVIEW_REQUIRED'
        ? [{ field: 'total_amount', champ: champ.total_amount, challenger: challenger.total_amount }]
        : [],
      math_ok: true,
    },
    processing_logs: [
      { agent: 'preprocessing', status: 'success', duration_ms: 320, at: base.created_at },
      { agent: 'champ_ocr_azure', status: 'success', duration_ms: 1840, at: base.created_at },
      { agent: 'challenger_ocr_paddle', status: 'success', duration_ms: 2210, at: base.created_at },
      { agent: 'validation', status: 'success', duration_ms: 28, at: base.created_at },
    ],
  };
}

function stats() {
  const counts = STATUSES.reduce((acc, s) => {
    acc[s.toLowerCase()] = INVOICES.filter((i) => i.status === s).length;
    return acc;
  }, {});
  const todayIso = new Date().toISOString().slice(0, 10);
  const processedToday = INVOICES.filter(
    (i) => i.created_at.slice(0, 10) === todayIso,
  ).length;
  return {
    total: INVOICES.length,
    uploaded: counts.uploaded || 0,
    processing: counts.processing || 0,
    auto_approved: counts.auto_approved || 0,
    review_required: counts.review_required || 0,
    approved: counts.approved || 0,
    rejected: counts.rejected || 0,
    posted: counts.posted || 0,
    failed: counts.failed || 0,
    processed_today: processedToday,
    total_amount: INVOICES.reduce((sum, i) => sum + i.total_amount, 0),
    auto_approval_rate: 0.62,
    avg_confidence: 0.88,
    avg_processing_seconds: 4.7,
    recent_week: Array.from({ length: 7 }, (_, i) => ({
      day: new Date(Date.now() - (6 - i) * 86400000).toISOString().slice(0, 10),
      count: 3 + ((i * 7) % 9),
    })),
  };
}

// ---------- Router ----------
function delay(data, status = 200) {
  return new Promise((resolve) => {
    setTimeout(() => resolve({
      data,
      status,
      statusText: status === 200 ? 'OK' : 'Error',
      headers: {},
      config: {},
    }), DELAY_MS);
  });
}

function matchPath(url, pattern) {
  // pattern like "/invoices/:id" → regex
  const re = new RegExp(
    '^' + pattern.replace(/:[^/]+/g, '([^/]+)') + '$',
  );
  const m = url.match(re);
  return m ? m.slice(1) : null;
}

function handle(config) {
  const method = (config.method || 'get').toLowerCase();
  // strip baseURL if present so we match relative paths
  const url = (config.url || '').replace(/^https?:\/\/[^/]+/, '').replace(config.baseURL || '', '');
  const body = typeof config.data === 'string' ? safeJson(config.data) : config.data || {};
  const params = config.params || {};

  // Auth
  if (method === 'post' && url === '/auth/login') {
    if (!body.email) return delay({ detail: 'Email required' }, 400);
    return delay({
      access_token: 'mock.access.' + Date.now(),
      refresh_token: 'mock.refresh.' + Date.now(),
      token_type: 'bearer',
    });
  }
  if (method === 'post' && url === '/auth/register') {
    return delay({ ...SEED_USER, email: body.email, full_name: body.full_name });
  }
  if (method === 'get' && url === '/auth/me') {
    return delay(SEED_USER);
  }
  if (method === 'post' && url === '/auth/refresh') {
    return delay({
      access_token: 'mock.access.' + Date.now(),
      refresh_token: 'mock.refresh.' + Date.now(),
      token_type: 'bearer',
    });
  }

  // Invoices
  if (method === 'get' && url === '/invoices/stats') {
    return delay(stats());
  }
  if (method === 'get' && url === '/invoices') {
    let items = [...INVOICES];
    if (params.status) items = items.filter((i) => i.status === params.status);
    if (params.vendor_name) items = items.filter((i) =>
      i.vendor_name.toLowerCase().includes(String(params.vendor_name).toLowerCase()));
    if (params.search) items = items.filter((i) =>
      (i.invoice_number + ' ' + i.vendor_name).toLowerCase()
        .includes(String(params.search).toLowerCase()));
    const page = Math.max(1, Number(params.page) || 1);
    const size = Math.max(1, Number(params.size) || 20);
    const start = (page - 1) * size;
    return delay({
      items: items.slice(start, start + size),
      total: items.length,
      page,
      size,
      pages: Math.max(1, Math.ceil(items.length / size)),
    });
  }
  const detailMatch = matchPath(url, '/invoices/:id');
  if (method === 'get' && detailMatch) {
    return delay(makeDetail(detailMatch[0]));
  }
  if (method === 'post' && url === '/invoices/upload') {
    const now = new Date().toISOString();
    const id = `invoice-${String(INVOICES.length).padStart(4, '0')}`;
    const created = {
      id,
      filename: 'mock-upload.pdf',
      vendor_name: 'Pending extraction...',
      invoice_number: null,
      invoice_date: null,
      currency: 'USD',
      subtotal: null,
      tax_amount: null,
      total_amount: null,
      status: 'PROCESSING',
      confidence_score: null,
      created_at: now,
      updated_at: now,
    };
    INVOICES.unshift(created);
    return delay(created, 201);
  }

  // Review actions
  const reviewMatch = matchPath(url, '/review/:id/action');
  if (method === 'post' && reviewMatch) {
    const id = reviewMatch[0];
    const current = makeDetail(id);
    const action = body.action;
    const map = { APPROVE: 'APPROVED', REJECT: 'REJECTED', REPROCESS: 'PROCESSING' };
    current.status = map[action] || current.status;
    return delay(current);
  }

  // Health
  if (url.startsWith('/health') || url === '/') {
    return delay({ status: 'ok', mock: true });
  }

  // Fallthrough — log so the dev can see what's missing
  // eslint-disable-next-line no-console
  console.warn('[mockServer] unhandled request', method.toUpperCase(), url);
  return delay({ detail: 'Mock: endpoint not implemented' }, 404);
}

function safeJson(s) {
  try { return JSON.parse(s); } catch { return {}; }
}

/** Axios adapter that replaces network calls with the mock router. */
export const mockAdapter = async (config) => {
  try {
    return await handle(config);
  } catch (e) {
    return Promise.reject({
      response: { status: 500, data: { detail: e?.message || 'mock error' } },
    });
  }
};
