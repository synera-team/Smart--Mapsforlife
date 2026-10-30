export function MapShell() {
    return (<>
      <div id="app" className="app">
        <header className="topbar">
          <button className="brand" id="brand" aria-label="Xanh24 - Maps for Life">
            <img src="/assets/logo.png" alt="Xanh24 - Maps for Life"/>
          </button>
          <div className="topbar-title" id="topTitle">
            <div className="tt-kicker" id="ttKicker">Bản đồ số</div>
            <div className="tt-main" id="ttMain">Thành phố Hà Nội</div>
          </div>
          <div className="searchbox" id="searchbox">
            <span className="sb-ic" data-icon="search"/>
            <input id="q" type="search" autoComplete="off" spellCheck={false} placeholder="Tìm địa điểm, cơ quan, phường…" aria-label="Tìm kiếm"/>
            <button className="sb-clear" id="qClear" aria-label="Xoá" hidden/>
          </div>
          <div className="topbar-right">
            <div className="clock" id="clock"><b id="clockTime">--:--</b><span id="clockDate"/></div>
            <button className="chip-btn lang" id="langBtn" aria-label="Ngôn ngữ">EN</button>
          </div>
        </header>

        <main className="stage">
          <aside className="panel" id="panel">
            <div className="sheet-handle" id="sheetHandle"><span /></div>
            <div className="panel-body" id="panelBody"/>
          </aside>
          <section className="mapwrap">
            <div id="map" className="map"/>
            <div className="map-ctrl" id="mapCtrl">
              <button className="mc" data-act="zin" aria-label="Phóng to"/>
              <button className="mc" data-act="zout" aria-label="Thu nhỏ"/>
              <button className="mc" data-act="here" aria-label="Vị trí của tôi"/>
              <button className="mc" data-act="layers" aria-label="Lớp bản đồ"/>
            </div>
            <div className="layer-pop" id="layerPop" hidden/>
            <div className="map-badge" id="mapBadge" hidden/>
          </section>
        </main>

        <footer className="footer" id="footer">
          <span id="copyright">Bản quyền thuộc về Công ty TNHH Công nghệ và Truyền thông Xanh24</span>
        </footer>
      </div>

      <div className="modal" id="modal" hidden>
        <div className="modal-back" data-close=""/>
        <div className="modal-card" id="modalCard"/>
      </div>

      <div className="idle" id="idle" hidden>
        <div className="idle-stage" id="idleStage"/>
        <div className="idle-top">
          <img src="/assets/logo.png" alt="Xanh24 - Maps for Life" className="idle-logo"/>
          <div className="idle-clock"><b id="idleTime">--:--</b><span id="idleDate"/></div>
        </div>
        <div className="idle-bottom">
          <div className="idle-dots" id="idleDots"/>
          <button className="idle-cta" id="idleCta">
            <span className="pulse"/>
            <span className="idle-cta-ic" data-icon="touch"/>
            <span className="idle-cta-text"><b id="idleCtaTitle">Chạm để mở Bản đồ</b><small id="idleCtaSub">Tìm địa điểm · Chỉ đường · Xe buýt & Metro · Gọi xe</small></span>
          </button>
          <div className="idle-quick" id="idleQuick"/>
        </div>
        <div className="idle-foot" id="idleFoot"/>
      </div>

      <div className="toast" id="toast" hidden/>
      <div className="osk" id="osk" hidden/>
    </>);
}
