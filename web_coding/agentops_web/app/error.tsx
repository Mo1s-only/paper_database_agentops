'use client';
import Link from 'next/link';
export default function ErrorPage({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return <main className="recovery-page"><span className="eyebrow">Connection interrupted</span><h1>暂时无法加载工作区</h1><p>数据服务可能离线、响应超时或配置不完整。恢复连接后可以重新加载。</p>{error.digest && <code>参考编号：{error.digest}</code>}<div><button className="button primary" onClick={retry}>重新加载</button><Link className="button secondary" href="/">返回首页</Link></div></main>;
}
