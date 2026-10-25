export default function Loading() {
  return <div className="workspace-loading" role="status" aria-label="正在加载工作区"><div className="skeleton heading-skeleton" /><div className="skeleton caption-skeleton" /><div className="loading-cards">{[1,2,3,4].map((i) => <div className="skeleton" key={i} />)}</div><div className="skeleton table-skeleton" /><span className="sr-only">正在加载数据…</span></div>;
}
