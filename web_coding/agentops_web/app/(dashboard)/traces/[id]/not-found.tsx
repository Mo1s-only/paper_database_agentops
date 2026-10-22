import { SearchX } from 'lucide-react';
import Link from 'next/link';

export default function TraceNotFound() {
  return <div className="not-found"><SearchX size={32} /><h1>Trace 不存在</h1><p>该记录可能已超过保留期，或 ID 不正确。</p><Link className="button primary" href="/traces">返回列表</Link></div>;
}
