import Link from 'next/link';
export default function NotFound() {
  return <main className="recovery-page"><span className="eyebrow">404 / Not found</span><h1>这个页面不存在</h1><p>链接可能已失效，你可以返回工作区继续查找执行记录。</p><Link className="button primary" href="/overview">返回总览</Link></main>;
}
