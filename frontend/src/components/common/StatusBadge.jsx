const LABELS = {
  UPLOADED: 'Uploaded',
  PROCESSING: 'Processing',
  AUTO_APPROVED: 'Auto-approved',
  REVIEW_REQUIRED: 'Needs review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  POSTED: 'Posted',
  FAILED: 'Failed',
};

export default function StatusBadge({ status }) {
  const klass = `badge badge--${(status || '').toLowerCase()}`;
  return <span className={klass}>{LABELS[status] || status}</span>;
}
