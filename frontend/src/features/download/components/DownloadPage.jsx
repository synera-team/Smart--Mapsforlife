import { useEffect, useState } from 'react';
import { qrSVG } from '../../../utils/qr.js';
function formatSize(bytes) {
    return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
async function readError(response, fallback) {
    const data = await response.json().catch(() => ({}));
    return data.error || fallback;
}
function AppCard({ file, selected }) {
    const target = new URL('/download', window.location.origin);
    target.searchParams.set('app', file.id);
    useEffect(() => {
        if (selected)
            document.querySelector('.app-card.is-selected')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, [selected]);
    return (<article className={`app-card${selected ? ' is-selected' : ''}`} data-file-id={file.id}>
      <div className="app-icon" aria-hidden="true">X</div>
      <div className="app-info">
        <h3>{file.title}</h3>
        <span className="version">Phiên bản {file.version}</span>
        <p className="app-meta">Android · {formatSize(file.size)} · APK</p>
        <p className="app-filename">{file.name}</p>
      </div>
      <a className="download-link" href={file.url} aria-label={`Tải ${file.name}`}>Tải ứng dụng <span aria-hidden="true">↓</span></a>
      <div className="qr-column">
        <div className="qr-image" aria-label={`Mã QR mở trang tải ${file.name}`} dangerouslySetInnerHTML={{ __html: qrSVG(target.toString(), { size: 76, margin: 3 }) }}/>
        <span className="qr-caption">Quét để mở trang này</span>
      </div>
    </article>);
}
export function DownloadPage() {
    const [catalog, setCatalog] = useState({ status: 'loading' });
    const [pin, setPin] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const selected = new URLSearchParams(window.location.search).get('app');
    async function loadCatalog() {
        const response = await fetch('/api/download/files', { credentials: 'same-origin' });
        if (response.status === 401) {
            setCatalog({ status: 'locked', error: '' });
            return;
        }
        if (!response.ok)
            throw new Error(await readError(response, 'Không thể tải danh sách ứng dụng'));
        const result = await response.json();
        setCatalog({ status: 'ready', files: result.files, error: '' });
    }
    useEffect(() => {
        void loadCatalog().catch(error => setCatalog({ status: 'locked', error: error.message }));
    }, []);
    async function unlock(event) {
        event.preventDefault();
        setSubmitting(true);
        try {
            const response = await fetch('/api/download/login', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin }),
            });
            if (!response.ok)
                throw new Error(await readError(response, 'Không thể xác thực mã PIN'));
            setPin('');
            await loadCatalog();
        }
        catch (error) {
            setCatalog({ status: 'locked', error: error instanceof Error ? error.message : String(error) });
        }
        finally {
            setSubmitting(false);
        }
    }
    async function lock() {
        try {
            const response = await fetch('/api/download/logout', { method: 'POST', credentials: 'same-origin' });
            if (!response.ok)
                throw new Error(await readError(response, 'Không thể khóa phiên tải xuống'));
            setCatalog({ status: 'locked', error: '' });
        }
        catch (error) {
            setCatalog(previous => previous.status === 'ready'
                ? { ...previous, error: error instanceof Error ? error.message : String(error) }
                : previous);
        }
    }
    return (<main className="page">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Về Xanh24 Maps for Life"><img src="/assets/logo.png" alt="Xanh24 Maps for Life"/></a>
        <a className="back-link" href="/">Về bản đồ <span aria-hidden="true">↗</span></a>
      </header>
      <section className="intro">
        <div className="eyebrow"><span className="status-dot"/> XANH24 · TRUNG TÂM TẢI ỨNG DỤNG</div>
        <h1>Cài đặt ứng dụng<br /><span>trên thiết bị của bạn.</span></h1>
        <p>Tải ứng dụng Android về điện thoại hoặc màn hình. Quét mã QR bằng điện thoại để mở nhanh trang này.</p>
      </section>
      {catalog.status === 'ready' ? (<section id="catalog-panel" className="catalog-panel" aria-labelledby="catalog-title">
          <div className="catalog-heading"><div><div className="eyebrow">DÀNH CHO ANDROID</div><h2 id="catalog-title">Ứng dụng khả dụng</h2></div>
            <button id="logout" className="logout-button" type="button" onClick={lock}>Khóa trang</button></div>
          {catalog.error && <p className="error-message" role="alert">{catalog.error}</p>}
          <div id="app-list" className="app-list" aria-live="polite">
            {catalog.files.map(file => <AppCard key={file.id} file={file} selected={file.id === selected}/>)}
          </div>
          {catalog.files.length === 0 && <p id="empty-state" className="empty-state">Chưa có tệp APK trong danh sách.</p>}
        </section>) : (<section id="login-panel" className="login-panel" aria-labelledby="login-title">
          <div className="lock-icon" aria-hidden="true">↗</div>
          <div className="login-copy"><h2 id="login-title">Trang tải có bảo vệ</h2><p>Nhập mã PIN được cấp để xem và tải các ứng dụng.</p></div>
          <form id="pin-form" className="pin-form" onSubmit={unlock}>
            <label className="sr-only" htmlFor="pin">Mã PIN</label>
            <input id="pin" name="pin" type="password" inputMode="numeric" autoComplete="off" placeholder="Nhập mã PIN" value={pin} onChange={event => setPin(event.target.value)} required/>
            <button id="unlock" type="submit" disabled={submitting || catalog.status === 'loading'}>{submitting ? 'Đang xác thực…' : 'Mở trang tải'} <span aria-hidden="true">→</span></button>
          </form>
          {catalog.status === 'locked' && catalog.error && <p id="login-error" className="error-message" role="alert">{catalog.error}</p>}
        </section>)}
      <footer className="footer"><span>© Xanh24 · Maps for Life</span><span>Chỉ cài đặt ứng dụng từ nguồn bạn tin cậy.</span></footer>
    </main>);
}
