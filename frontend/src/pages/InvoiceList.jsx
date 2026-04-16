import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useSearchParams } from 'react-router-dom';
import { format } from 'date-fns';

import StatusBadge from '../components/common/StatusBadge.jsx';
import { SkeletonTable } from '../components/common/Skeleton.jsx';
import {
  fetchInvoices,
  resetFilters,
  setFilter,
} from '../store/slices/invoicesSlice.js';

const STATUSES = [
  '',
  'UPLOADED',
  'PROCESSING',
  'AUTO_APPROVED',
  'REVIEW_REQUIRED',
  'APPROVED',
  'POSTED',
  'REJECTED',
  'FAILED',
];

export default function InvoiceList() {
  const dispatch = useDispatch();
  const [params] = useSearchParams();
  const { list, filters, listStatus } = useSelector((s) => s.invoices);

  // Pick up ?status= from query-string (e.g. from Dashboard quick links)
  useEffect(() => {
    const statusParam = params.get('status');
    if (statusParam && statusParam !== filters.status) {
      dispatch(setFilter({ status: statusParam }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    dispatch(fetchInvoices());
  }, [dispatch, filters]);

  const onFilter = (patch) => dispatch(setFilter(patch));

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Invoices</h1>
          <div className="page-header__subtitle">
            {list.total} total · page {list.page} of {list.pages}
          </div>
        </div>
        <button className="btn btn--ghost" onClick={() => dispatch(resetFilters())}>
          Clear filters
        </button>
      </div>

      <div className="filter-bar">
        <input
          className="input"
          placeholder="Search vendor, invoice #, filename…"
          value={filters.search}
          onChange={(e) => onFilter({ search: e.target.value })}
        />
        <select
          className="select"
          value={filters.status}
          onChange={(e) => onFilter({ status: e.target.value })}
        >
          <option value="">All statuses</option>
          {STATUSES.filter(Boolean).map((s) => (
            <option key={s} value={s}>
              {s.replace('_', ' ')}
            </option>
          ))}
        </select>
        <input
          className="input"
          type="date"
          value={filters.date_from}
          onChange={(e) => onFilter({ date_from: e.target.value })}
          placeholder="From"
        />
        <input
          className="input"
          type="date"
          value={filters.date_to}
          onChange={(e) => onFilter({ date_to: e.target.value })}
          placeholder="To"
        />
        <select
          className="select"
          value={`${filters.sort_by}:${filters.sort_dir}`}
          onChange={(e) => {
            const [sort_by, sort_dir] = e.target.value.split(':');
            onFilter({ sort_by, sort_dir });
          }}
        >
          <option value="created_at:desc">Newest first</option>
          <option value="created_at:asc">Oldest first</option>
          <option value="total_amount:desc">Amount (high → low)</option>
          <option value="total_amount:asc">Amount (low → high)</option>
          <option value="vendor_name:asc">Vendor (A → Z)</option>
        </select>
      </div>

      {listStatus === 'loading' && list.items.length === 0 ? (
        <SkeletonTable />
      ) : list.items.length === 0 ? (
        <div className="empty-state">
          No invoices match these filters. Try widening your search.
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table table--interactive">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Vendor</th>
                <th>Date</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((inv) => (
                <tr
                  key={inv.id}
                  onClick={() => (window.location.href = `/invoices/${inv.id}`)}
                >
                  <td>
                    <Link to={`/invoices/${inv.id}`}>
                      {inv.invoice_number || <span className="muted">—</span>}
                    </Link>
                    <div className="muted mono" style={{ fontSize: 11 }}>
                      {inv.original_filename}
                    </div>
                  </td>
                  <td>{inv.vendor_name || <span className="muted">—</span>}</td>
                  <td>
                    {inv.invoice_date
                      ? format(new Date(inv.invoice_date), 'MMM d, yyyy')
                      : '—'}
                  </td>
                  <td>
                    {inv.total_amount
                      ? `${inv.currency || 'USD'} ${Number(inv.total_amount).toLocaleString(undefined, {
                          minimumFractionDigits: 2,
                        })}`
                      : '—'}
                  </td>
                  <td>
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className="muted">
                    {format(new Date(inv.created_at), 'MMM d, HH:mm')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pagination">
        <span className="pagination__info">
          Page {list.page} / {list.pages}
        </span>
        <button
          onClick={() => onFilter({ page: Math.max(1, list.page - 1) })}
          disabled={list.page <= 1}
        >
          Previous
        </button>
        <button
          onClick={() => onFilter({ page: Math.min(list.pages, list.page + 1) })}
          disabled={list.page >= list.pages}
        >
          Next
        </button>
      </div>
    </>
  );
}
