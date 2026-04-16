import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import toast from 'react-hot-toast';

import { authApi, tokenStorage } from '../../services/api.js';

const initialState = {
  user: null,
  status: 'idle',        // idle | loading | authenticated | error
  initialized: false,    // has the initial "me" check completed?
  error: null,
};

export const login = createAsyncThunk(
  'auth/login',
  async ({ email, password }, { rejectWithValue }) => {
    try {
      const tokens = await authApi.login(email, password);
      tokenStorage.set(tokens);
      const user = await authApi.me();
      toast.success(`Welcome back, ${user.full_name}`);
      return user;
    } catch (err) {
      const msg = err.response?.data?.message || 'Login failed';
      toast.error(msg);
      return rejectWithValue(msg);
    }
  },
);

export const loadSession = createAsyncThunk(
  'auth/loadSession',
  async (_, { rejectWithValue }) => {
    if (!tokenStorage.get()) return null;
    try {
      return await authApi.me();
    } catch {
      tokenStorage.clear();
      return rejectWithValue('Session expired');
    }
  },
);

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    logout(state) {
      tokenStorage.clear();
      state.user = null;
      state.status = 'idle';
    },
  },
  extraReducers: (b) => {
    b.addCase(login.pending, (s) => {
      s.status = 'loading';
      s.error = null;
    });
    b.addCase(login.fulfilled, (s, a) => {
      s.user = a.payload;
      s.status = 'authenticated';
      s.initialized = true;
    });
    b.addCase(login.rejected, (s, a) => {
      s.status = 'error';
      s.error = a.payload;
    });
    b.addCase(loadSession.fulfilled, (s, a) => {
      s.user = a.payload;
      s.status = a.payload ? 'authenticated' : 'idle';
      s.initialized = true;
    });
    b.addCase(loadSession.rejected, (s) => {
      s.user = null;
      s.status = 'idle';
      s.initialized = true;
    });
  },
});

export const { logout } = authSlice.actions;
export default authSlice.reducer;
