import { configureStore } from '@reduxjs/toolkit';

import authReducer from './slices/authSlice.js';
import invoicesReducer from './slices/invoicesSlice.js';
import uiReducer from './slices/uiSlice.js';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    invoices: invoicesReducer,
    ui: uiReducer,
  },
  devTools: import.meta.env.MODE !== 'production',
});
