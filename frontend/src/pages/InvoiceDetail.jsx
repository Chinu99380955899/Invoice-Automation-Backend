import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { Link, useParams } from 'react-router-dom';
import { format } from 'date-fns';

import StatusBadge from '../components/common/StatusBadge.jsx';
import { SkeletonCard } from '../components/common/Skeleton.jsx';
import {
  clearCurrent,
  fetchInvoiceDetail,
  submitReviewAction,
} from '../store/slices/invoicesSlice.js';

const EDITABLE = [
  { key: 'vendor_name', label: 'Vendor name' },
  { key: 'invoice_number', label: 'Invoice number' },
  { key: 'invoice_date', label: 'Invoice date', type: 'date' },
  { key: 'due_date', label: 'Due date', type: 'date' },
  { key: 'purchase_order', label: 'Purchase order' },
  { key: 'currency', label: 'Currency' },
  { key: 'subtotal', label: 'Subtotal', type: 'number' },
  { key: 'tax_amount', label: 'Tax amount', type: 'number' },
  { key: 'total_amount', label: 'Total amount', type: 'number' },
];

function asInputDate(v) {
  if (!v) return '';
  try {
    return format(new Date(v), 'yyyy-MM-dd');
  } catch {
    return '';
  }
}

export default function InvoiceDetail() {
  const { id } = useParams();
  const dispatch = useDispatch();
  const { current, currentStatus } = useSelector((s) => s.invoices);
  const [form, setForm] = useState({});
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    dispatch(fetchInvoiceDetail(id));
    return () => dispatch(clearCurrent());
  }, [dispatch, id]);

  useEffect(() => {
    if (current) {
      setForm({
        vendor_name: current.vendor_name || '',
        invoice_number: current.invoice_number || '',
        invoice_date: asInputDate(current.invoice_date),
        due_date: asInputDate(current.due_date),
        purchase_order: current.purchase_order || '',
        currency: current.currency || 'USD',
        subtotal: current.subtotal || '',
        tax_amount: current.tax_amount || '',
        total_amount: current.total_amount || '',
      });
      setNotes(current.review_notes || '');
    }
  }, [current]);

  const mismatches = useMemo(() => {
    if (!current?.validation_report?.fields) return {};
    const out = {};
    for (const [k, v] of Object.entries(current.validation_report.fields)) {
      if (!v.match) out[k] = true;
    }
    return out;
  }, [current]);

  if (!current) {
    return currentStatus === 'loading' ? (
      <>
        <SkeletonCard lines={4} />
        <div style={{ height: 16 }} />
        <SkeletonCard lines={6} />
      </>
    ) : (
      <div className="empty-state">Invoice not found.</div>
    );
  }

  const handleAction = async (action) => {
    setSaving(true);
    const dirty =
      form.vendor_name !== (current.vendor_name || '') ||
      form.invoice_number !== (current.invoice_number || '') ||
      asInputDate(current.invoice_date) !== form.invoice_date ||
      String(current.total_amount || '') !== String(form.total_amount);
    const payload = {
      action,
      notes: notes || undefined,
      updates: dirty
        ? {
            vendor_name: form.vendor_name || null,
            invoice_number: form.invoice_number || null,
            invoice_date: form.invoice_date || null,
            due_date: form.due_date || null,
            purchase_order: form.purchase_order || null,
            currency: form.currency || null,
            subtotal: form.subtotal || null,
            tax_amount: form.tax_amount || null,
            total_amount: form.total_amount || null,
          }
        : undefined,
    };
    await dispatch(submitReviewAction({ invoiceId: current.id, payload }));
    setSaving(false);
  };

  const canReview =
    current.status === 'REVIEW_REQUIRED' || current.status === 'FAILED';

  return (
    <>
      <div className="page-header">
        <div>
          <h1>
            {current.invoice_number || 'Unknown invoice'}{' '}
            <StatusBadge status={current.status} />
          </h1>
          <div className="page-header__subtitle">
            {current.original_filename} · Uploaded{' '}
            {format(new Date(current.created_at), 'MMM d, yyyy HH:mm')}
          </div>
        </div>
        <div className="row">
          <Link to="/invoices" className="btn btn--ghost">
            ← Back
          </Link>
        </div>
      </div>

      {current.error_message && (
        <div className="card" style={{ borderColor: 'var(--color-danger)', background: 'var(--color-danger-soft)', color: '#7f1d1d' }}>
          <strong>Error:</strong> {current.error_message}
        </div>
      )}

      <div className="grid-2 section">
        <div className="card">
          <h2 className="card__title">Extracted fields</h2>
          <div>
            {EDITABLE.map((f) => (
              <div
                className={`form-control ${mismatches[f.key] ? 'ocr-field--mismatch' : ''}`}
                key={f.key}
              >
                <label>
                  {f.label}
                  {mismatches[f.key] && (
                    <span style={{ color: '#a16207', marginLeft: 8 }}>
                      ⚠ OCR mismatch
                    </span>
                  )}
                </label>
                <input
                  className="input"
                  type={f.type || 'text'}
                  value={form[f.key] ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, [f.key]: e.target.value })
                  }
                  disabled={!canReview && current.status !== 'APPROVED'}
                />
              </div>
            ))}
          </div>
        </div>

        <div className="stack">
          <div className="card">
            <h2 className="card__title">Validation report</h2>
            {current.validation_report ? (
              <>
                <div className="row" style={{ justifyContent: 'space-between' }}>
                  <div>
                    <div className="muted">Decision</div>
                    <strong>
                      {current.validation_report.decision || '—'}
                    </strong>
                  </div>
                  <div>
                    <div className="muted">Confidence</div>
                    <strong>
                      {(current.validation_report.weighted_confidence ?? 0) * 100}%
                    </strong>
                  </div>
                  <div>
                    <div className="muted">Agreement</div>
                    <strong>
                      {Math.round(
                        (current.validation_report.agreement_ratio ?? 0) * 100,
                      )}
                      %
                    </strong>
                  </div>
                </div>
                {current.validation_report.reasons?.length ? (
                  <ul style={{ marginTop: 12, paddingLeft: 20 }}>
                    {current.validation_report.reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : (
              <div className="muted">No validation report yet.</div>
            )}
          </div>

          {canReview && (
            <div className="card">
              <h2 className="card__title">Review action</h2>
              <div className="form-control">
                <label>Notes (optional)</label>
                <textarea
                  className="textarea"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Add context about this decision…"
                />
              </div>
              <div className="row">
                <button
                  className="btn btn--success"
                  disabled={saving}
                  onClick={() => handleAction('APPROVE')}
                >
                  Approve &amp; post
                </button>
                <button
                  className="btn btn--danger"
                  disabled={saving}
                  onClick={() => handleAction('REJECT')}
                >
                  Reject
                </button>
                <button
                  className="btn btn--secondary"
                  disabled={saving}
                  onClick={() => handleAction('REPROCESS')}
                >
                  Reprocess
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="section">
        <h2 className="card__title" style={{ marginLeft: 4 }}>
          Champ vs Challenger
        </h2>
        <div className="ocr-compare">
          <OcrPanel
            title="Champ — Azure DI"
            data={current.champ_ocr_raw}
            mismatches={mismatches}
          />
          <OcrPanel
            title="Challenger — PaddleOCR"
            data={current.challenger_ocr_raw}
            mismatches={mismatches}
          />
        </div>
      </div>

      <div className="card section">
        <h2 className="card__title">Line items</h2>
        {current.items?.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {current.items
                .slice()
                .sort((a, b) => a.line_number - b.line_number)
                .map((i) => (
                  <tr key={i.id}>
                    <td>{i.line_number}</td>
                    <td>{i.description}</td>
                    <td>{Number(i.quantity).toString()}</td>
                    <td>{Number(i.unit_price).toFixed(2)}</td>
                    <td>{Number(i.amount).toFixed(2)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">No line items extracted.</div>
        )}
      </div>

      <div className="card section">
        <h2 className="card__title">Processing audit trail</h2>
        {current.logs?.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Agent</th>
                <th>Level</th>
                <th>Message</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              {current.logs.map((l) => (
                <tr key={l.id}>
                  <td className="muted mono">
                    {format(new Date(l.created_at), 'HH:mm:ss.SSS')}
                  </td>
                  <td>{l.agent}</td>
                  <td>
                    <span className={`badge badge--${l.level.toLowerCase()}`}>
                      {l.level}
                    </span>
                  </td>
                  <td>{l.message}</td>
                  <td className="muted">{l.duration_ms ? `${l.duration_ms} ms` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">No processing logs yet.</div>
        )}
      </div>
    </>
  );
}

function OcrPanel({ title, data, mismatches }) {
  const fields = [
    ['vendor_name', 'Vendor'],
    ['invoice_number', 'Invoice #'],
    ['invoice_date', 'Date'],
    ['subtotal', 'Subtotal'],
    ['tax_amount', 'Tax'],
    ['total_amount', 'Total'],
    ['purchase_order', 'PO'],
  ];
  return (
    <div className="ocr-compare__col">
      <h4>{title}</h4>
      {data ? (
        fields.map(([k, label]) => (
          <div
            key={k}
            className={`ocr-field ${mismatches[k] ? 'ocr-field--mismatch' : ''}`}
          >
            <span className="ocr-field__label">{label}</span>
            <span className="ocr-field__value">{formatCell(data[k])}</span>
          </div>
        ))
      ) : (
        <div className="muted">No output (engine unavailable).</div>
      )}
      {data?.confidence_scores && (
        <div className="muted" style={{ marginTop: 12, fontSize: 12 }}>
          Avg confidence:{' '}
          {(
            Object.values(data.confidence_scores).reduce((a, b) => a + (b || 0), 0) /
            Math.max(1, Object.keys(data.confidence_scores).length)
          ).toFixed(2)}
        </div>
      )}
    </div>
  );
}

function formatCell(v) {
  if (v == null || v === '') return '—';
  if (typeof v === 'number') return v.toFixed(2);
  return String(v);
}
