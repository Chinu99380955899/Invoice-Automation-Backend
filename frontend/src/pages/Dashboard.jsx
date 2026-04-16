import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import UploadDropzone from '../components/invoice/UploadDropzone.jsx';
import { SkeletonCard } from '../components/common/Skeleton.jsx';
import { fetchStats } from '../store/slices/invoicesSlice.js';

const STAT_CARDS = [
  { key: 'total', label: 'Total invoices', variant: 'primary' },
  { key: 'auto_approved', label: 'Auto-approved', variant: 'success' },
  { key: 'review_required', label: 'Needs review', variant: 'warning' },
  { key: 'failed', label: 'Failed', variant: 'danger' },
  { key: 'posted', label: 'Posted to SAP', variant: 'info' },
  { key: 'processed_today', label: 'Processed today', variant: 'primary' },
];

const PIE_COLORS = {
  auto_approved: '#16a34a',
  approved: '#22c55e',
  review_required: '#ca8a04',
  posted: '#0284c7',
  processing: '#7c3aed',
  failed: '#dc2626',
  rejected: '#b91c1c',
  uploaded: '#64748b',
};

export default function Dashboard() {
  const dispatch = useDispatch();
  const { stats, statsStatus } = useSelector((s) => s.invoices);

  useEffect(() => {
    dispatch(fetchStats());
    const id = setInterval(() => dispatch(fetchStats()), 15000);
    return () => clearInterval(id);
  }, [dispatch]);

  const pieData = stats
    ? Object.entries({
        auto_approved: stats.auto_approved,
        approved: stats.approved,
        review_required: stats.review_required,
        posted: stats.posted,
        processing: stats.processing,
        failed: stats.failed,
        rejected: stats.rejected,
        uploaded: stats.uploaded,
      })
        .filter(([, v]) => v > 0)
        .map(([k, v]) => ({ name: k.replace('_', ' '), key: k, value: v }))
    : [];

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <div className="page-header__subtitle">
            Real-time overview of invoice processing pipeline
          </div>
        </div>
        <div className="row">
          <Link to="/invoices" className="btn btn--secondary">
            View invoices
          </Link>
          <Link to="/review" className="btn btn--primary">
            Review queue
          </Link>
        </div>
      </div>

      {!stats && statsStatus === 'loading' ? (
        <div className="stats-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} lines={2} />
          ))}
        </div>
      ) : (
        <div className="stats-grid">
          {STAT_CARDS.map((c) => (
            <div key={c.key} className={`stat-card stat-card--${c.variant}`}>
              <div className="stat-card__accent" />
              <div className="stat-card__label">{c.label}</div>
              <div className="stat-card__value">{stats?.[c.key] ?? 0}</div>
              {c.key === 'total' && (
                <div className="stat-card__delta">
                  Avg processing:{' '}
                  {stats?.avg_processing_seconds
                    ? `${stats.avg_processing_seconds.toFixed(1)}s`
                    : '—'}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="grid-2 section">
        <div className="card">
          <h2 className="card__title">Upload invoices</h2>
          <UploadDropzone />
        </div>
        <div className="card">
          <h2 className="card__title">Status distribution</h2>
          {pieData.length ? (
            <div style={{ width: '100%', height: 260 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={50}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {pieData.map((entry) => (
                      <Cell key={entry.key} fill={PIE_COLORS[entry.key] || '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-state">No invoices yet — upload one to get started.</div>
          )}
        </div>
      </div>

      <div className="card">
        <h2 className="card__title">Quick actions</h2>
        <div className="row">
          <Link to="/invoices?status=REVIEW_REQUIRED" className="btn btn--secondary">
            View review queue
          </Link>
          <Link to="/invoices?status=FAILED" className="btn btn--secondary">
            Failed invoices
          </Link>
          <Link to="/invoices?status=POSTED" className="btn btn--secondary">
            Recently posted
          </Link>
        </div>
      </div>
    </>
  );
}
