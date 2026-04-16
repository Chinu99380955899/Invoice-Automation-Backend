import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import toast from 'react-hot-toast';

import { invoiceApi, reviewApi } from '../../services/api.js';

const initialState = {
  list: { items: [], total: 0, page: 1, size: 20, pages: 1 },
  listStatus: 'idle',
  filters: {
    status: '',
    search: '',
    vendor_name: '',
    date_from: '',
    date_to: '',
    page: 1,
    size: 20,
    sort_by: 'created_at',
    sort_dir: 'desc',
  },
  stats: null,
  statsStatus: 'idle',
  current: null,
  currentStatus: 'idle',
  uploading: false,
  uploadProgress: 0,
  error: null,
};

export const fetchInvoices = createAsyncThunk(
  'invoices/list',
  async (_, { getState, rejectWithValue }) => {
    try {
      const { filters } = getState().invoices;
      const params = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v !== '' && v !== null && v !== undefined),
      );
      return await invoiceApi.list(params);
    } catch (err) {
      return rejectWithValue(err.response?.data?.message || 'Failed to load invoices');
    }
  },
);

export const fetchInvoiceDetail = createAsyncThunk(
  'invoices/detail',
  async (id, { rejectWithValue }) => {
    try {
      return await invoiceApi.get(id);
    } catch (err) {
      return rejectWithValue(err.response?.data?.message || 'Failed to load invoice');
    }
  },
);

export const fetchStats = createAsyncThunk('invoices/stats', async (_, { rejectWithValue }) => {
  try {
    return await invoiceApi.stats();
  } catch (err) {
    return rejectWithValue(err.response?.data?.message || 'Failed to load stats');
  }
});

export const uploadInvoice = createAsyncThunk(
  'invoices/upload',
  async (file, { dispatch, rejectWithValue }) => {
    try {
      const result = await invoiceApi.upload(file, (pct) =>
        dispatch(setUploadProgress(pct)),
      );
      toast.success(`Uploaded ${file.name}`);
      return result;
    } catch (err) {
      const msg = err.response?.data?.message || 'Upload failed';
      toast.error(msg);
      return rejectWithValue(msg);
    }
  },
);

export const submitReviewAction = createAsyncThunk(
  'invoices/review',
  async ({ invoiceId, payload }, { rejectWithValue }) => {
    try {
      const result = await reviewApi.action(invoiceId, payload);
      toast.success(`Invoice ${payload.action.toLowerCase()}d`);
      return result;
    } catch (err) {
      const msg = err.response?.data?.message || 'Review action failed';
      toast.error(msg);
      return rejectWithValue(msg);
    }
  },
);

const invoicesSlice = createSlice({
  name: 'invoices',
  initialState,
  reducers: {
    setFilter(state, { payload }) {
      state.filters = { ...state.filters, ...payload };
      if (!('page' in payload)) state.filters.page = 1;
    },
    resetFilters(state) {
      state.filters = initialState.filters;
    },
    setUploadProgress(state, { payload }) {
      state.uploadProgress = payload;
    },
    clearCurrent(state) {
      state.current = null;
      state.currentStatus = 'idle';
    },
  },
  extraReducers: (b) => {
    b.addCase(fetchInvoices.pending, (s) => {
      s.listStatus = 'loading';
    });
    b.addCase(fetchInvoices.fulfilled, (s, a) => {
      s.list = a.payload;
      s.listStatus = 'idle';
    });
    b.addCase(fetchInvoices.rejected, (s, a) => {
      s.listStatus = 'error';
      s.error = a.payload;
    });

    b.addCase(fetchInvoiceDetail.pending, (s) => {
      s.currentStatus = 'loading';
    });
    b.addCase(fetchInvoiceDetail.fulfilled, (s, a) => {
      s.current = a.payload;
      s.currentStatus = 'idle';
    });
    b.addCase(fetchInvoiceDetail.rejected, (s, a) => {
      s.currentStatus = 'error';
      s.error = a.payload;
    });

    b.addCase(fetchStats.pending, (s) => {
      s.statsStatus = 'loading';
    });
    b.addCase(fetchStats.fulfilled, (s, a) => {
      s.stats = a.payload;
      s.statsStatus = 'idle';
    });

    b.addCase(uploadInvoice.pending, (s) => {
      s.uploading = true;
      s.uploadProgress = 0;
    });
    b.addCase(uploadInvoice.fulfilled, (s) => {
      s.uploading = false;
      s.uploadProgress = 100;
    });
    b.addCase(uploadInvoice.rejected, (s) => {
      s.uploading = false;
      s.uploadProgress = 0;
    });

    b.addCase(submitReviewAction.fulfilled, (s, a) => {
      s.current = a.payload;
    });
  },
});

export const { setFilter, resetFilters, setUploadProgress, clearCurrent } =
  invoicesSlice.actions;
export default invoicesSlice.reducer;
