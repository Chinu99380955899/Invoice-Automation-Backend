import axios from 'axios';
import toast from 'react-hot-toast';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

const api = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Dev-only: replace the network layer with an in-memory mock so the UI
// can be demoed without the backend running. Top-level await guarantees
// the adapter is installed before any downstream module fires a request.
if (USE_MOCK) {
  const { mockAdapter } = await import('./mockServer.js');
  api.defaults.adapter = mockAdapter;
  // eslint-disable-next-line no-console
  console.info('[api] VITE_USE_MOCK_API=true — using in-memory mock adapter');
}

const TOKEN_KEY = 'invoice.access_token';
const REFRESH_KEY = 'invoice.refresh_token';

export const tokenStorage = {
  get: () => localStorage.getItem(TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: ({ access_token, refresh_token }) => {
    if (access_token) localStorage.setItem(TOKEN_KEY, access_token);
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

// --- Attach JWT to every request ---
api.interceptors.request.use((config) => {
  const token = tokenStorage.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// --- Consistent error surfacing + auto-refresh on 401 (once) ---
let refreshPromise = null;

async function refreshToken() {
  if (refreshPromise) return refreshPromise;
  const refresh = tokenStorage.getRefresh();
  if (!refresh) throw new Error('No refresh token');
  refreshPromise = axios
    .post(`${baseURL}/auth/refresh`, null, { params: { refresh_token: refresh } })
    .then(({ data }) => {
      tokenStorage.set(data);
      return data.access_token;
    })
    .finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config || {};
    const status = error.response?.status;

    if (status === 401 && !original._retried && tokenStorage.getRefresh()) {
      original._retried = true;
      try {
        const newToken = await refreshToken();
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      } catch (refreshErr) {
        tokenStorage.clear();
        window.location.assign('/login');
        return Promise.reject(refreshErr);
      }
    }

    // Surface a friendly toast for network/server errors.
    if (!error.response) {
      toast.error('Network error — check your connection');
    } else if (status >= 500) {
      toast.error('Server error. Please try again.');
    }
    return Promise.reject(error);
  },
);

// --- Typed helpers ---
export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }).then((r) => r.data),
  register: (data) => api.post('/auth/register', data).then((r) => r.data),
  me: () => api.get('/auth/me').then((r) => r.data),
};

export const invoiceApi = {
  list: (params) => api.get('/invoices', { params }).then((r) => r.data),
  get: (id) => api.get(`/invoices/${id}`).then((r) => r.data),
  stats: () => api.get('/invoices/stats').then((r) => r.data),
  upload: (file, onProgress) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post('/invoices/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded * 100) / e.total));
        },
      })
      .then((r) => r.data);
  },
};

export const reviewApi = {
  action: (invoiceId, payload) =>
    api.post(`/review/${invoiceId}/action`, payload).then((r) => r.data),
};

export default api;
