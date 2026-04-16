import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';

import StatusBadge from '../components/common/StatusBadge.jsx';
import { SkeletonTable } from '../components/common/Skeleton.jsx';
import { fetchInvoices, setFilter } from '../store/slices/invoicesSlice.js';

export default function ReviewQueue() {
  const dispatch = useDispatch();
  const { list, listStatus } = useSelector((s) => s.invoices);

  useEffect(() => {
    dispatch(setFilter({ status: 'REVIEW_REQUIRED', page: 1, size: 50 }));
    dispatch(fetchInvoices());
  }, [dispatch]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Review queue</h1>
          <div className="page-header__subtitle">
            Invoices flagged by the validation engine for human review.
          </div>
        </div>
      </div>

      {listStatus === 'loading' ? (
        <SkeletonTable />
      ) : list.items.length === 0 ? (
        <div className="empty-state">
          🎉 Queue is empty — no invoices currently need review.
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table className="table">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Vendor</th>
                <th>Amount</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {list.items.map((inv) => (
                <tr key={inv.id}>
                  <td>{inv.invoice_number || '—'}</td>
                  <td>{inv.vendor_name || '—'}</td>
                  <td>
                    {inv.total_amount
                      ? `${inv.currency || 'USD'} ${Number(inv.total_amount).toLocaleString()}`
                      : '—'}
                  </td>
                  <td>
                    {inv.confidence_score != null
                      ? `${(Number(inv.confidence_score) * 100).toFixed(1)}%`
                      : '—'}
                  </td>
                  <td>
                    <StatusBadge status={inv.status} />
                  </td>
                  <td className="muted">
                    {format(new Date(inv.created_at), 'MMM d, HH:mm')}
                  </td>
                  <td>
                    <Link to={`/invoices/${inv.id}`} className="btn btn--primary">
                      Review
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
