import { useEffect, useState } from 'react';
const params = new URLSearchParams(window.location.search);
const provider = window.location.pathname.split('/').pop() === 'go.html'
    ? params.get('provider') || 'grab'
    : window.location.pathname.split('/').pop() || 'grab';
const lat = Number.parseFloat(params.get('lat') || '');
const lng = Number.parseFloat(params.get('lng') || '');
const name = params.get('name') || '';
const address = params.get('addr') || '';
function storeUrl(config) {
    const ua = navigator.userAgent;
    if (/iPhone|iPad|iPod/i.test(ua))
        return config.ios_store;
    if (/Android/i.test(ua))
        return config.android_store;
    return config.web || config.android_store;
}
function fill(template) {
    return (template || '').replaceAll('{lat}', String(lat)).replaceAll('{lng}', String(lng))
        .replaceAll('{name}', encodeURIComponent(name)).replaceAll('{addr}', encodeURIComponent(address || name));
}
async function copyDestination() {
    const text = [name, address].filter(Boolean).join(', ') || `${lat},${lng}`;
    try {
        await navigator.clipboard.writeText(text);
    }
    catch {
        const field = document.createElement('textarea');
        field.value = text;
        document.body.append(field);
        field.select();
        document.execCommand('copy');
        field.remove();
    }
}
async function openApplication(config) {
    const deep = fill(config.app_url);
    const fallback = storeUrl(config);
    if (!config.onelink)
        await copyDestination();
    if (config.onelink && deep) {
        window.location.href = config.onelink.replaceAll('{deeplink}', encodeURIComponent(deep));
        return;
    }
    if (/Android/i.test(navigator.userAgent) && config.android_package) {
        window.location.href = `intent://open#Intent;package=${config.android_package};S.browser_fallback_url=${encodeURIComponent(fallback || config.web || '')};end`;
        return;
    }
    if (deep) {
        const started = Date.now();
        window.location.href = deep;
        window.setTimeout(() => {
            if (Date.now() - started < 2200 && !document.hidden && fallback)
                window.location.href = fallback;
        }, 1600);
        return;
    }
    if (fallback || config.web)
        window.location.href = fallback || config.web;
}
export function RidePage() {
    const [config, setConfig] = useState({});
    const [copyright, setCopyright] = useState('Bản quyền thuộc về Công ty TNHH Công nghệ và Truyền thông Xanh24');
    const [copied, setCopied] = useState(false);
    const label = config.name || provider;
    useEffect(() => {
        let active = true;
        fetch('/api/public/bootstrap')
            .then(response => response.json())
            .then((data) => {
            if (!active)
                return;
            const next = data.settings?.ride?.[provider] || {};
            setConfig(next);
            if (data.settings?.copyright)
                setCopyright(data.settings.copyright);
            if (next.onelink && /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)) {
                window.setTimeout(() => { void openApplication(next); }, 500);
            }
        }).catch(() => { });
        return () => { active = false; };
    }, []);
    useEffect(() => { document.title = `Đặt ${label} · Xanh24`; }, [label]);
    async function copy() {
        await copyDestination();
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
    }
    return (<>
      <header><img src="/assets/logo.png" alt="Xanh24 - Maps for Life"/></header>
      <main>
        <div className="card"><div className="kick">Đặt xe {label} tới</div><h1>{name || 'Điểm đến'}</h1><div className="addr">{address}</div>
          <div className="coords">{Number.isFinite(lat) && Number.isFinite(lng) ? `${lat.toFixed(6)}, ${lng.toFixed(6)}` : ''}</div></div>
        <div className="card">
          <button className={`btn pri ${provider}`} onClick={() => { void openApplication(config); }}>Mở ứng dụng {label}</button>
          <a className="btn sec" href={storeUrl(config) || '#'}>Tải ứng dụng {label}</a>
          <button className="btn sec" onClick={copy}>Sao chép địa chỉ điểm đến</button>
          <a className="btn sec" href={`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`} target="_blank" rel="noopener">Xem trên Google Maps</a>
          <p className="note">{config.onelink
            ? 'Nếu ứng dụng không tự mở điểm đến, hãy dán địa chỉ đã sao chép vào ô “Điểm đến” trong ứng dụng.'
            : `${label} chưa hỗ trợ điền sẵn điểm đến qua liên kết: khi bấm “Mở ứng dụng”, địa chỉ điểm đến được sao chép sẵn — hãy dán vào ô Điểm đến.`}</p>
        </div>
      </main>
      <footer>{copyright}</footer>
      {copied && <div className="ok" role="status">Đã sao chép</div>}
    </>);
}
