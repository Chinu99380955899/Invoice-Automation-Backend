import { describe, expect, it } from 'vitest';

import invoicesReducer, {
  setFilter,
  resetFilters,
  setUploadProgress,
} from '../store/slices/invoicesSlice.js';
import uiReducer, { toggleSidebar } from '../store/slices/uiSlice.js';

describe('invoicesSlice', () => {
  it('updates filters and resets to page 1 when non-page field changes', () => {
    const state = invoicesReducer(undefined, setFilter({ status: 'FAILED' }));
    expect(state.filters.status).toBe('FAILED');
    expect(state.filters.page).toBe(1);
  });

  it('preserves page when only page changes', () => {
    let state = invoicesReducer(undefined, setFilter({ status: 'FAILED' }));
    state = invoicesReducer(state, setFilter({ page: 3 }));
    expect(state.filters.page).toBe(3);
    expect(state.filters.status).toBe('FAILED');
  });

  it('resetFilters restores defaults', () => {
    let state = invoicesReducer(undefined, setFilter({ status: 'APPROVED', page: 5 }));
    state = invoicesReducer(state, resetFilters());
    expect(state.filters.status).toBe('');
    expect(state.filters.page).toBe(1);
  });

  it('tracks upload progress', () => {
    const state = invoicesReducer(undefined, setUploadProgress(42));
    expect(state.uploadProgress).toBe(42);
  });
});

describe('uiSlice', () => {
  it('toggles the sidebar', () => {
    let state = uiReducer(undefined, toggleSidebar());
    expect(state.sidebarCollapsed).toBe(true);
    state = uiReducer(state, toggleSidebar());
    expect(state.sidebarCollapsed).toBe(false);
  });
});
