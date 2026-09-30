"""Khởi tạo dữ liệu nền: danh mục, cấu hình mặc định, ranh giới 50 phường/xã đã số hoá,
điểm trụ sở hành chính (lấy từ ký hiệu trên bản đồ gốc), địa danh mẫu, tuyến metro, quảng cáo mẫu.
Chỉ chạy các phần còn trống — an toàn khi gọi lại nhiều lần.
"""
import json
import os
import secrets

from db import ex, get_setting, now, q, set_setting
from geoutil import point_in_geom

HERE = os.path.dirname(os.path.abspath(__file__))

CATEGORIES = [
    ("hanh-chinh", "Cơ quan hành chính", "Government", "building", "#14346F"),
    ("dich-vu-cong", "Dịch vụ công", "Public services", "doc", "#2A62B8"),
    ("y-te", "Y tế", "Healthcare", "cross", "#E5484D"),
    ("giao-duc", "Giáo dục", "Education", "school", "#7C5CD6"),
    ("di-tich", "Di tích – Văn hoá", "Heritage & culture", "temple", "#C9861A"),
    ("du-lich", "Du lịch – Giải trí", "Tourism & leisure", "camera", "#E0663A"),
    ("cong-vien", "Công viên – Không gian xanh", "Parks", "tree", "#17A673"),
    ("mua-sam", "Mua sắm – Chợ", "Shopping & markets", "bag", "#D6457A"),
    ("an-uong", "Ẩm thực", "Food & drink", "food", "#E08A1E"),
    ("luu-tru", "Lưu trú", "Accommodation", "bed", "#5B6BD6"),
    ("giao-thong", "Giao thông", "Transport", "bus", "#0E8FB0"),
    ("tien-ich", "Tiện ích công cộng", "Public amenities", "star", "#4B5B76"),
]

DEFAULT_SETTINGS = {
    "app_name": "Xanh24 - Maps for Life",
    "app_short": "Maps for Life",
    "org_name": "Công ty TNHH Công nghệ và Truyền thông Xanh24",
    "copyright": "Bản quyền thuộc về Công ty TNHH Công nghệ và Truyền thông Xanh24",
    "region_name": "Thành phố Hà Nội",
    "idle_timeout": 40,
    "idle_warning": 6,
    "default_center": [105.8342, 21.0278],
    "default_zoom": 12.3,
    "languages": ["vi", "en"],
    "tiles": {
        "active": "ofm-liberty",
        "options": [
            {"id": "ofm-liberty", "name": "OpenFreeMap Liberty (nguồn mở, mặc định)", "style": "https://tiles.openfreemap.org/styles/liberty"},
            {"id": "ofm-positron", "name": "OpenFreeMap Positron (sáng, tối giản)", "style": "https://tiles.openfreemap.org/styles/positron"},
            {"id": "ofm-bright", "name": "OpenFreeMap Bright", "style": "https://tiles.openfreemap.org/styles/bright"},
            {"id": "osm", "name": "OpenStreetMap chuẩn (raster)",
             "tiles": ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
             "tileSize": 256, "attribution": "© OpenStreetMap contributors", "maxzoom": 19},
            {"id": "esri-sat", "name": "Ảnh vệ tinh — Esri",
             "tiles": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
             "tileSize": 256, "attribution": "© Esri, Maxar, Earthstar Geographics", "maxzoom": 19},
        ],
        "satellite": "esri-sat",
    },
    "routing": {
        "provider": "osrm",
        "foot": "https://routing.openstreetmap.de/routed-foot",
        "bike": "https://routing.openstreetmap.de/routed-bike",
        "driving": "https://routing.openstreetmap.de/routed-car",
        "timeout": 8,
        "note": "Máy chủ định tuyến công cộng FOSSGIS chỉ dùng thử. Khi vận hành thật nên tự dựng OSRM/Valhalla với dữ liệu Việt Nam.",
    },
    "ride": {
        "grab": {"enabled": True, "name": "Grab",
                 "app_url": "grab://open?screenType=BOOKING&dropOffLatitude={lat}&dropOffLongitude={lng}&dropOffKeywords={name}",
                 "onelink": "https://grab.onelink.me/2695613898?af_dp={deeplink}&af_force_deeplink=true&af_web_dp=https%3A%2F%2Fwww.grab.com%2Fvn%2Fdownload%2F",
                 "android_store": "https://play.google.com/store/apps/details?id=com.grabtaxi.passenger",
                 "ios_store": "https://apps.apple.com/vn/app/grab-app/id647268330",
                 "web": "https://www.grab.com/vn/transport/"},
        "xanhsm": {"enabled": True, "name": "Xanh SM",
                   "android_package": "com.gsm.customer",
                   "android_store": "https://play.google.com/store/apps/details?id=com.gsm.customer",
                   "ios_store": "https://apps.apple.com/vn/app/id6446425595",
                   "web": "https://www.xanhsm.com/",
                   "hotline": "1900 2088"},
    },
    "transit": {
        "google_url": "https://www.google.com/maps/dir/?api=1&origin={from_lat},{from_lng}&destination={lat},{lng}&travelmode=transit",
        "walk_radius_m": 900,
        "overpass": ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"],
    },
    "kiosk_app": {"version": "1.3.0", "version_code": 4, "apk_url": "/downloads/Xanh24-Kiosk-1.3.0.apk"},
    "geocode": {"enabled": True, "reverse_url": "https://nominatim.openstreetmap.org/reverse", "pick_hint": True},
    "kiosk": {"on_screen_keyboard": True, "show_clock": True, "show_ward_boundaries": True,
              "start_screen": "idle", "admin_exit_pin": "2424"},
    "public_base_url": "",
}

# Địa danh mẫu (toạ độ WGS84 tham khảo — cần cán bộ xác minh trước khi vận hành)
SAMPLE_POIS = [
    ("Hồ Hoàn Kiếm (Hồ Gươm)", "cong-vien", 21.0288, 105.8525, "Đinh Tiên Hoàng, Hoàn Kiếm", "Không gian công cộng trung tâm của Thủ đô, gắn với truyền thuyết trả gươm.", True),
    ("Đền Ngọc Sơn", "di-tich", 21.0307, 105.8524, "Đinh Tiên Hoàng, Hoàn Kiếm", "Di tích lịch sử – văn hoá trên đảo Ngọc, nối với bờ bằng cầu Thê Húc.", True),
    ("Nhà thờ Lớn Hà Nội", "di-tich", 21.0287, 105.8490, "40 Nhà Chung, Hoàn Kiếm", "Nhà thờ chính toà Thánh Giuse, kiến trúc Gothic cuối thế kỷ XIX.", False),
    ("Chợ Đồng Xuân", "mua-sam", 21.0381, 105.8494, "Đồng Xuân, Hoàn Kiếm", "Chợ đầu mối lâu đời nhất khu phố cổ.", False),
    ("Nhà hát Lớn Hà Nội", "di-tich", 21.0243, 105.8575, "1 Tràng Tiền", "Công trình kiến trúc Pháp đầu thế kỷ XX, nơi biểu diễn nghệ thuật.", True),
    ("Văn Miếu – Quốc Tử Giám", "di-tich", 21.0293, 105.8355, "58 Quốc Tử Giám", "Trường đại học đầu tiên của Việt Nam, di tích quốc gia đặc biệt.", True),
    ("Lăng Chủ tịch Hồ Chí Minh", "di-tich", 21.0368, 105.8346, "Quảng trường Ba Đình", "Công trình tưởng niệm Chủ tịch Hồ Chí Minh tại Quảng trường Ba Đình.", True),
    ("Hoàng thành Thăng Long", "di-tich", 21.0353, 105.8403, "19C Hoàng Diệu", "Di sản văn hoá thế giới UNESCO.", True),
    ("Chùa Một Cột", "di-tich", 21.0359, 105.8336, "Chùa Một Cột, Ba Đình", "Ngôi chùa có kiến trúc độc đáo, biểu tượng của Hà Nội.", False),
    ("Chùa Trấn Quốc", "di-tich", 21.0480, 105.8368, "Thanh Niên, Tây Hồ", "Ngôi chùa cổ bên Hồ Tây.", True),
    ("Ga Hà Nội", "giao-thong", 21.0245, 105.8412, "120 Lê Duẩn", "Nhà ga đường sắt trung tâm Thủ đô.", False),
    ("Công viên Thống Nhất", "cong-vien", 21.0155, 105.8440, "Trần Nhân Tông", "Công viên lớn trong nội đô.", False),
    ("Bệnh viện Bạch Mai", "y-te", 21.0015, 105.8410, "78 Giải Phóng", "Bệnh viện đa khoa trung ương hạng đặc biệt.", False),
    ("Bảo tàng Dân tộc học Việt Nam", "du-lich", 21.0405, 105.7986, "Nguyễn Văn Huyên", "Trưng bày văn hoá 54 dân tộc Việt Nam.", False),
    ("Bến xe Mỹ Đình", "giao-thong", 21.0283, 105.7782, "20 Phạm Hùng", "Bến xe khách liên tỉnh.", False),
    ("Sân vận động Quốc gia Mỹ Đình", "du-lich", 21.0205, 105.7639, "Lê Đức Thọ", "Sân vận động quốc gia.", False),
    ("Trung tâm Hội nghị Quốc gia", "hanh-chinh", 21.0063, 105.7870, "57 Phạm Hùng", "Nơi tổ chức các sự kiện, hội nghị lớn.", False),
    ("Phủ Tây Hồ", "di-tich", 21.0590, 105.8195, "Đặng Thai Mai, Tây Hồ", "Di tích tín ngưỡng thờ Mẫu bên Hồ Tây.", False),
    ("Cầu Long Biên", "di-tich", 21.0430, 105.8590, "Đầu cầu phía Hoàn Kiếm", "Cây cầu thép lịch sử bắc qua sông Hồng.", False),
    ("Bảo tàng Hà Nội", "du-lich", 21.0080, 105.7880, "Phạm Hùng", "Bảo tàng lịch sử – văn hoá Thủ đô.", False),
]

# Metro — toạ độ ga tham khảo (verified=0), quản trị S1 cần hiệu chỉnh theo thực địa
METRO = [
    {"code": "2A", "name": "Tuyến 2A Cát Linh – Hà Đông", "color": "#2E9E5B", "status": "operating",
     "operator": "Hanoi Metro", "info": "Tuyến đường sắt trên cao, 12 ga.",
     "stops": [("Cát Linh", 21.0292, 105.8267), ("La Thành", 21.0217, 105.8216), ("Thái Hà", 21.0147, 105.8197),
               ("Láng", 21.0067, 105.8163), ("Thượng Đình", 20.9989, 105.8132), ("Vành Đai 3", 20.9918, 105.8053),
               ("Phùng Khoang", 20.9859, 105.7942), ("Văn Quán", 20.9789, 105.7879), ("Hà Đông", 20.9730, 105.7810),
               ("La Khê", 20.9688, 105.7700), ("Văn Khê", 20.9616, 105.7622), ("Yên Nghĩa", 20.9501, 105.7482)]},
    {"code": "3", "name": "Tuyến 3 Nhổn – Ga Hà Nội (đoạn trên cao)", "color": "#D6453D", "status": "operating",
     "operator": "Hanoi Metro", "info": "Đoạn trên cao Nhổn – Cầu Giấy. Đoạn ngầm Kim Mã – Ga Hà Nội cập nhật theo tiến độ.",
     "stops": [("Nhổn", 21.0513, 105.7348), ("Minh Khai", 21.0470, 105.7443), ("Phú Diễn", 21.0431, 105.7524),
               ("Cầu Diễn", 21.0395, 105.7627), ("Lê Đức Thọ", 21.0376, 105.7705), ("Đại học Quốc gia", 21.0369, 105.7825),
               ("Chùa Hà", 21.0365, 105.7922), ("Cầu Giấy", 21.0336, 105.7998)]},
]

SAMPLE_ADS = [
    {"title": "Xanh24 – Maps for Life", "duration_sec": 10, "priority": 10,
     "html": "<div class='ad-hero ad-g1'><div class='ad-kicker'>Bản đồ số hành chính</div><h1>Tìm đường tới mọi<br>địa điểm công cộng</h1><p>Tra cứu cơ quan hành chính, y tế, giáo dục, di tích… và nhận lộ trình ngay trên điện thoại.</p></div>"},
    {"title": "Dịch vụ công trực tuyến", "duration_sec": 10, "priority": 5,
     "html": "<div class='ad-hero ad-g2'><div class='ad-kicker'>Chính quyền số</div><h1>Nộp hồ sơ trực tuyến,<br>không cần xếp hàng</h1><p>Chạm vào màn hình để xem vị trí Bộ phận Một cửa và Trung tâm Phục vụ hành chính công gần nhất.</p></div>"},
    {"title": "Không gian quảng cáo", "duration_sec": 8, "priority": 1,
     "html": "<div class='ad-hero ad-g3'><div class='ad-kicker'>Hợp tác truyền thông</div><h1>Không gian quảng cáo<br>trên màn hình tương tác</h1><p>Liên hệ Xanh24 để đặt nội dung tại các điểm màn hình công cộng.</p></div>"},
]

DEFAULT_MODULES = [
    {"key": "weather", "name": "Thời tiết", "description": "Module mẫu dạng iframe — kết nối nhà cung cấp thời tiết.",
     "kind": "iframe", "entry_url": "/modules/sample/weather.html", "icon": "sun", "color": "#E0A21E", "enabled": 1, "sort": 1},
    {"key": "feedback", "name": "Phản ánh – Góp ý", "description": "Cổng dự phòng: kết nối hệ thống tiếp nhận phản ánh hiện trường.",
     "kind": "iframe", "entry_url": "/modules/sample/feedback.html", "icon": "chat", "color": "#2A62B8", "enabled": 1, "sort": 2},
    {"key": "events", "name": "Sự kiện – Tin tức", "description": "Cổng dự phòng: lịch sự kiện, thông báo của phường.",
     "kind": "iframe", "entry_url": "", "icon": "calendar", "color": "#17A673", "enabled": 0, "sort": 3},
    {"key": "dvc", "name": "Dịch vụ công", "description": "Liên kết Cổng Dịch vụ công quốc gia (mở qua QR trên điện thoại).",
     "kind": "link", "entry_url": "https://dichvucong.gov.vn", "icon": "doc", "color": "#14346F", "enabled": 1, "sort": 4},
]


def seed_all(log=print):
    # --- settings
    for k, v in DEFAULT_SETTINGS.items():
        if get_setting(k) is None:
            set_setting(k, v)
    # --- categories
    if not q("SELECT 1 FROM categories LIMIT 1"):
        for i, (cid, name, en, icon, color) in enumerate(CATEGORIES):
            ex("INSERT INTO categories(id,name,name_en,icon,color,sort) VALUES(?,?,?,?,?,?)", (cid, name, en, icon, color, i))
        log("  + danh mục")
    # --- wards
    gj_path = os.path.join(HERE, "wards_seed.geojson")
    wards = []
    if os.path.exists(gj_path):
        gj = json.load(open(gj_path, encoding="utf-8"))
        wards = gj["features"]
        if not q("SELECT 1 FROM wards LIMIT 1"):
            for ft in wards:
                p = ft["properties"]
                ex("""INSERT INTO wards(slug,name,short,type,area_km2,geometry,hq,source,scan_image,info,published,updated_at,updated_by)
                      VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                   (p["slug"], p["name"], p["short"], p["type"], p["area_km2"], json.dumps(ft["geometry"]),
                    json.dumps(p.get("hq")), p["source"], f"/assets/maps/{p['slug']}.jpg",
                    json.dumps({"fit_rms_m": p.get("fit_rms_m")}), now(), "seed"))
            log(f"  + {len(wards)} ranh giới phường/xã")
    # --- POIs
    if not q("SELECT 1 FROM pois LIMIT 1"):
        n = 0
        wrows = [(w["slug"], json.loads(w["geometry"])) for w in q("SELECT slug,geometry FROM wards")]

        def ward_of(lat, lng):
            for slug, g in wrows:
                if point_in_geom(lng, lat, g):
                    return slug
            return None

        for w in q("SELECT slug,name,hq FROM wards"):
            hq = json.loads(w["hq"] or "null")
            if not hq:
                continue
            _ins_poi(dict(name=f"Trụ sở UBND {w['name']}", category="hanh-chinh", lat=hq[1], lng=hq[0], ward_slug=w["slug"],
                          address=w["name"] + ", Hà Nội",
                          description="Trung tâm hành chính cấp xã theo bản đồ phương án thành lập đơn vị hành chính (Sở Nội vụ TP Hà Nội).",
                          extra={"source": "Ký hiệu 'Trung tâm hành chính cấp xã' trên bản đồ gốc", "verify": True}))
            n += 1
        for name, cat, lat, lng, addr, desc, feat in SAMPLE_POIS:
            _ins_poi(dict(name=name, category=cat, lat=lat, lng=lng, ward_slug=ward_of(lat, lng), address=addr + ", Hà Nội",
                          description=desc, featured=1 if feat else 0,
                          extra={"source": "Dữ liệu mẫu — cần xác minh", "verify": True}))
            n += 1
        log(f"  + {n} địa điểm mẫu")
    # --- transit
    if not q("SELECT 1 FROM transit_lines LIMIT 1"):
        for line in METRO:
            ids = []
            for (name, lat, lng) in line["stops"]:
                ids.append(ex("INSERT INTO transit_stops(kind,name,lat,lng,lines,note,verified) VALUES('metro',?,?,?,?,?,0)",
                              (f"Ga {name}", lat, lng, json.dumps([line["code"]]), "Toạ độ tham khảo")))
            geom = {"type": "LineString", "coordinates": [[s[2], s[1]] for s in line["stops"]]}
            ex("INSERT INTO transit_lines(kind,code,name,color,operator,status,info,stops,geometry,updated_at) VALUES('metro',?,?,?,?,?,?,?,?,?)",
               (line["code"], line["name"], line["color"], line["operator"], line["status"], line["info"], json.dumps(ids), json.dumps(geom), now()))
        log("  + tuyến metro")
    # --- ads
    if not q("SELECT 1 FROM ads LIMIT 1"):
        for a in SAMPLE_ADS:
            ex("INSERT INTO ads(title,media_type,html,duration_sec,priority,status,created_at,updated_at) VALUES(?,?,?,?,?,'published',?,?)",
               (a["title"], "html", a["html"], a["duration_sec"], a["priority"], now(), now()))
        log("  + quảng cáo mẫu")
    # --- modules
    if not q("SELECT 1 FROM modules LIMIT 1"):
        for m in DEFAULT_MODULES:
            ex("INSERT INTO modules(key,name,description,kind,entry_url,icon,color,enabled,sort,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (m["key"], m["name"], m["description"], m["kind"], m["entry_url"], m["icon"], m["color"], m["enabled"], m["sort"], now()))
    # --- demo device
    if not q("SELECT 1 FROM devices LIMIT 1"):
        hk = q("SELECT hq FROM wards WHERE slug='hoan-kiem'", one=True)
        hq = json.loads(hk["hq"]) if hk and hk["hq"] else [105.8503, 21.0301]
        ex("INSERT INTO devices(code,name,ward_slug,address,lat,lng,created_at) VALUES(?,?,?,?,?,?,?)",
           ("HK-01", "Màn hình UBND phường Hoàn Kiếm", "hoan-kiem", "Sảnh Bộ phận Một cửa", hq[1], hq[0], now()))
    # --- initial admin
    if not q("SELECT 1 FROM users LIMIT 1"):
        from auth import hash_password
        pw = os.environ.get("XANH24_ADMIN_PASSWORD") or ("X24-" + secrets.token_urlsafe(9))
        ex("INSERT INTO users(username,password_hash,full_name,role,must_change_password,created_at) VALUES(?,?,?,?,1,?)",
           ("admin", hash_password(pw), "Quản trị hệ thống", "S0", now()))
        from db import DATA_DIR
        with open(os.path.join(DATA_DIR, "INITIAL_ADMIN.txt"), "w") as f:
            f.write(f"Tài khoản S0 khởi tạo\nusername: admin\npassword: {pw}\nĐổi mật khẩu ngay sau lần đăng nhập đầu tiên rồi xoá file này.\n")
        log(f"  + tài khoản admin (mật khẩu trong data/INITIAL_ADMIN.txt)")


def _ins_poi(d):
    t = now()
    pid = ex("""INSERT INTO pois(ward_slug,category,name,address,description,lat,lng,featured,extra,status,created_at,updated_at,published_at,published_by)
                VALUES(?,?,?,?,?,?,?,?,?,'published',?,?,?,'seed')""",
             (d.get("ward_slug"), d["category"], d["name"], d.get("address", ""), d.get("description", ""), d["lat"], d["lng"],
              d.get("featured", 0), json.dumps(d.get("extra", {}), ensure_ascii=False), t, t, t))
    ex("UPDATE pois SET code=? WHERE id=?", (f"X24-{pid:05d}", pid))
    return pid
