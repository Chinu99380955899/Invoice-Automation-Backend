export function SkeletonLine({ width = '100%', height = 14, style = {} }) {
  return <div className="skeleton" style={{ width, height, ...style }} />;
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="card" aria-label="Loading content">
      <SkeletonLine width="40%" height={18} style={{ marginBottom: 16 }} />
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine
          key={i}
          width={`${70 + ((i * 13) % 30)}%`}
          style={{ marginBottom: 10 }}
        />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 6, cols = 5 }) {
  return (
    <div className="card" aria-label="Loading table">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
          {Array.from({ length: cols }).map((__, c) => (
            <SkeletonLine key={c} height={16} />
          ))}
        </div>
      ))}
    </div>
  );
}
