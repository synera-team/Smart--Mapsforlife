"""Nhập dữ liệu địa điểm từ Excel theo biểu mẫu.

Hỗ trợ ảnh theo 4 cách:
  1. Ảnh chèn nổi (Insert > Picture) đặt trong dòng dữ liệu (Excel / LibreOffice / WPS).
  2. Ảnh "Place in Cell" của Excel 365 (richData).
  3. Ảnh nhúng ô của WPS Office (=DISPIMG("ID_..",1)).
  4. Tên tệp ảnh trong gói .zip tải kèm, hoặc đường link http(s).
"""
import io
import json
import re
import unicodedata
import uuid
import zipfile
import xml.etree.ElementTree as ET

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from db import q
from geoutil import haversine_m, point_in_geom
from media import IMAGE_EXT, save_image_bytes

COLUMNS = [
    # key, header, width, required, note
    ("code", "Mã địa điểm", 14, False, "Để trống khi thêm mới. Điền mã (VD: X24-00012) để cập nhật địa điểm đã có."),
    ("name", "Tên địa điểm *", 32, True, "Tên chính thức hiển thị trên bản đồ."),
    ("category", "Danh mục *", 24, True, "Chọn trong danh sách (sheet DANH_MUC)."),
    ("ward", "Phường/Xã", 20, False, "Để trống: hệ thống tự xác định theo toạ độ và ranh giới."),
    ("address", "Địa chỉ", 34, False, ""),
    ("lat", "Vĩ độ (lat) *", 13, True, "VD: 21.028511. Có thể dán '21.0285, 105.8542' hoặc link Google Maps vào cột này."),
    ("lng", "Kinh độ (lng) *", 13, True, "VD: 105.854222"),
    ("phone", "Điện thoại", 16, False, ""),
    ("hours", "Giờ mở cửa", 22, False, "VD: 08:00–17:00 (T2–T6)"),
    ("website", "Website", 26, False, ""),
    ("description", "Mô tả / Nội dung", 48, False, "Nội dung giới thiệu, thủ tục, lưu ý..."),
    ("image", "Ảnh đại diện", 18, False, "Chèn ảnh trực tiếp vào ô / dòng này, hoặc ghi tên tệp trong .zip, hoặc link ảnh."),
    ("gallery", "Ảnh khác", 26, False, "Nhiều tên tệp/link, cách nhau bởi dấu ; — ảnh chèn thêm trong dòng cũng được nhận."),
    ("vr_type", "VR360 – Loại", 16, False, "Ảnh 360 | Nhúng (iframe) | Video 360"),
    ("vr_url", "VR360 – Link/Tệp", 34, False, "Link tour (Kuula, Matterport, 3DVista...) hoặc tên tệp ảnh 360 trong .zip"),
    ("tags", "Từ khoá", 20, False, "Cách nhau bởi dấu phẩy — giúp tìm kiếm"),
    ("name_en", "Tên tiếng Anh", 26, False, ""),
    ("featured", "Nổi bật (x)", 10, False, "Đánh x để ưu tiên hiển thị"),
]
KEYS = [c[0] for c in COLUMNS]
VR_TYPES = {"anh 360": "pano", "anh360": "pano", "pano": "pano", "panorama": "pano", "nhung (iframe)": "embed", "nhung": "embed",
            "iframe": "embed", "embed": "embed", "tour": "embed", "video 360": "video", "video": "video"}


def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    s = s.replace("đ", "d")
    return re.sub(r"\s+", " ", s).strip()


def _norm_vi(s):
    s = str(s or "").replace("Đ", "D").replace("đ", "d")
    return norm(s)


HEADER_ALIASES = {k: {_norm_vi(h.replace("*", "")), k} for k, h, *_ in COLUMNS}
HEADER_ALIASES["lat"] |= {"vi do", "lat", "latitude"}
HEADER_ALIASES["lng"] |= {"kinh do", "lng", "lon", "longitude"}
HEADER_ALIASES["name"] |= {"ten", "ten dia diem"}
HEADER_ALIASES["description"] |= {"mo ta", "noi dung"}
HEADER_ALIASES["image"] |= {"anh", "hinh anh", "anh dai dien"}


# ------------------------------------------------------------------ embedded images
def _xml(z, name):
    try:
        return ET.fromstring(z.read(name))
    except KeyError:
        return None


def _rels(z, name):
    root = _xml(z, name)
    out = {}
    if root is not None:
        for r in root:
            out[r.get("Id")] = r.get("Target")
    return out


def _resolve(base, target):
    if target.startswith("/"):
        return target[1:]
    parts = base.split("/")[:-1]
    for seg in target.split("/"):
        if seg == "..":
            parts.pop()
        elif seg != ".":
            parts.append(seg)
    return "/".join(parts)


def excel365_cell_images(data):
    """Trả về {(sheet_xml_path, 'L5'): bytes} cho ảnh Place-in-Cell."""
    out = {}
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        return out
    names = set(z.namelist())
    if "xl/richData/rdrichvalue.xml" not in names:
        return out
    ns_main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    # rich value -> rel index
    rv_root = _xml(z, "xl/richData/rdrichvalue.xml")
    rv_rel = []
    for rv in rv_root:
        vals = [v.text for v in rv if v.tag.endswith("}v")]
        rv_rel.append(int(vals[0]) if vals and (vals[0] or "").isdigit() else None)
    rel_root = _xml(z, "xl/richData/richValueRel.xml")
    rel_ids = []
    if rel_root is not None:
        for r in rel_root:
            rel_ids.append(r.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"))
    rel_map = _rels(z, "xl/richData/_rels/richValueRel.xml.rels")
    # metadata: vm index -> rich value index
    vm_to_rv = {}
    md = _xml(z, "xl/metadata.xml")
    if md is not None:
        fut = []
        for fm in md.iter(ns_main + "futureMetadata"):
            for bk in fm.iter(ns_main + "bk"):
                rvb = [e for e in bk.iter() if e.tag.endswith("}rvb")]
                fut.append(int(rvb[0].get("i")) if rvb else None)
        vmeta = md.find(ns_main + "valueMetadata")
        if vmeta is not None:
            for i, bk in enumerate(vmeta.findall(ns_main + "bk"), start=1):
                rc = bk.find(ns_main + "rc")
                v = int(rc.get("v")) if rc is not None else i - 1
                vm_to_rv[i] = fut[v] if v < len(fut) and fut[v] is not None else v
    wb_rels = _rels(z, "xl/_rels/workbook.xml.rels")
    wb = _xml(z, "xl/workbook.xml")
    for sh in wb.iter(ns_main + "sheet"):
        rid = sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        path = _resolve("xl/workbook.xml", wb_rels.get(rid, ""))
        root = _xml(z, path)
        if root is None:
            continue
        for c in root.iter(ns_main + "c"):
            vm = c.get("vm")
            if not vm:
                continue
            try:
                rv_idx = vm_to_rv.get(int(vm), int(vm) - 1)
                rel_idx = rv_rel[rv_idx]
                target = rel_map[rel_ids[rel_idx]]
                media = _resolve("xl/richData/richValueRel.xml", target)
                out[(sh.get("name"), c.get("r"))] = z.read(media)
            except Exception:
                continue
    return out


def wps_cell_images(data):
    """Ảnh nhúng ô WPS: {ID: bytes}"""
    out = {}
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        root = _xml(z, "xl/cellimages.xml")
        if root is None:
            return out
        rels = _rels(z, "xl/_rels/cellimages.xml.rels")
        for pic in root.iter():
            if not pic.tag.endswith("}pic"):
                continue
            name = None
            embed = None
            for e in pic.iter():
                if e.tag.endswith("}cNvPr"):
                    name = e.get("name")
                if e.tag.endswith("}blip"):
                    embed = e.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
            if name and embed and embed in rels:
                out[name] = z.read(_resolve("xl/cellimages.xml", rels[embed]))
    except Exception:
        pass
    return out


# ------------------------------------------------------------------ parsing
def _find_header(ws):
    for r in range(1, min(ws.max_row, 15) + 1):
        mapping = {}
        for c in range(1, ws.max_column + 1):
            v = _norm_vi(ws.cell(r, c).value).replace("*", "").strip()
            if not v:
                continue
            for k, aliases in HEADER_ALIASES.items():
                if v in aliases and k not in mapping:
                    mapping[k] = c
                    break
        if "name" in mapping and ("lat" in mapping or "lng" in mapping):
            return r, mapping
    return None, None


COORD_RE = re.compile(r"(-?\d{1,3}\.\d+)\s*[, ]\s*(-?\d{1,3}\.\d+)")


def parse_coords(lat_v, lng_v):
    def f(v):
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", ".") if str(v).count(",") == 1 and "." not in str(v) else str(v).strip()
        try:
            return float(s)
        except ValueError:
            return None
    lat, lng = f(lat_v), f(lng_v)
    if lat is None and lat_v:
        s = str(lat_v)
        m = re.search(r"@(-?\d+\.\d+),(-?\d+\.\d+)", s) or re.search(r"[?&](?:q|query|ll|destination)=(-?\d+\.\d+),(-?\d+\.\d+)", s) or COORD_RE.search(s)
        if m:
            lat, lng = float(m.group(1)), float(m.group(2))
    if lat is not None and lng is not None and lat > 90 and lng < 90:
        lat, lng = lng, lat  # người dùng nhập ngược
    return lat, lng


def _cats():
    out = {}
    for c in q("SELECT id,name,name_en FROM categories WHERE active=1"):
        for key in (c["id"], c["name"], c["name_en"]):
            if key:
                out[_norm_vi(key)] = c["id"]
    return out


def _wards():
    rows = q("SELECT slug,name,short,geometry FROM wards")
    idx = {}
    geoms = []
    for w in rows:
        for key in (w["slug"], w["name"], w["short"], "phuong " + (w["short"] or ""), "xa " + (w["short"] or "")):
            idx[_norm_vi(key)] = w["slug"]
        if w["geometry"]:
            geoms.append((w["slug"], json.loads(w["geometry"])))
    return idx, geoms


def parse_workbook(xlsx_bytes, zip_bytes=None, batch_id=None):
    batch_id = batch_id or uuid.uuid4().hex[:12]
    wb_v = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    wb_f = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=False)
    ws = None
    hdr_row = mapping = None
    for name in wb_v.sheetnames:
        r, m = _find_header(wb_v[name])
        if r:
            ws, hdr_row, mapping = wb_v[name], r, m
            ws_f = wb_f[name]
            break
    if ws is None:
        raise ValueError("Không tìm thấy dòng tiêu đề hợp lệ (cần cột 'Tên địa điểm' và 'Vĩ độ/Kinh độ'). Hãy dùng biểu mẫu mẫu.")

    zfiles = {}
    if zip_bytes:
        try:
            zz = zipfile.ZipFile(io.BytesIO(zip_bytes))
            for n in zz.namelist():
                if n.endswith("/"):
                    continue
                base = n.split("/")[-1]
                zfiles[_norm_vi(base)] = (base, zz.read(n))
        except zipfile.BadZipFile:
            raise ValueError("Tệp .zip ảnh không hợp lệ")

    # ảnh nổi theo dòng
    float_imgs = {}
    for img in getattr(ws_f, "_images", []):
        try:
            anc = img.anchor._from
            row = anc.row + 1
            col = anc.col + 1
            float_imgs.setdefault(row, []).append((col, img._data()))
        except Exception:
            continue
    cell365 = excel365_cell_images(xlsx_bytes)
    wps = wps_cell_images(xlsx_bytes)

    cats = _cats()
    widx, wgeoms = _wards()
    existing = {r["code"]: r for r in q("SELECT id,code,name,lat,lng FROM pois WHERE code IS NOT NULL")}
    all_pois = q("SELECT id,code,name,lat,lng FROM pois WHERE status!='archived'")

    rows = []
    image_cache = {}

    def store(data, kind="image"):
        key = hash(data)
        if key not in image_cache:
            image_cache[key] = save_image_bytes(data, kind=kind, sub=f"import/{batch_id}")
        return image_cache[key]

    def resolve_ref(ref, kind="image"):
        ref = str(ref or "").strip()
        if not ref:
            return None, None
        if ref.lower().startswith(("http://", "https://")):
            return {"url": ref, "thumb": ref}, None
        hit = zfiles.get(_norm_vi(ref))
        if not hit:
            # thử không phần mở rộng
            for k, v in zfiles.items():
                if k.rsplit(".", 1)[0] == _norm_vi(ref).rsplit(".", 1)[0]:
                    hit = v
                    break
        if not hit:
            return None, f"Không tìm thấy tệp '{ref}' trong gói .zip"
        if "." + hit[0].rsplit(".", 1)[-1].lower() not in IMAGE_EXT:
            return None, f"Tệp '{ref}' không phải ảnh"
        try:
            return store(hit[1], kind), None
        except Exception:
            return None, f"Không đọc được ảnh '{ref}'"

    for r in range(hdr_row + 1, ws.max_row + 1):
        raw = {k: ws.cell(r, c).value for k, c in mapping.items()}
        if all(v in (None, "") for v in raw.values()) and r not in float_imgs:
            continue
        # bỏ dòng ví dụ/ghi chú
        if str(raw.get("name") or "").strip().lower().startswith(("ví dụ", "vd:", "#")):
            continue
        errors, warnings = [], []
        d = {"code": str(raw.get("code") or "").strip() or None,
             "name": str(raw.get("name") or "").strip(),
             "address": str(raw.get("address") or "").strip(),
             "phone": str(raw.get("phone") or "").strip(),
             "hours": str(raw.get("hours") or "").strip(),
             "website": str(raw.get("website") or "").strip(),
             "description": str(raw.get("description") or "").strip(),
             "tags": str(raw.get("tags") or "").strip(),
             "name_en": str(raw.get("name_en") or "").strip(),
             "featured": 1 if str(raw.get("featured") or "").strip().lower() in ("x", "1", "co", "có", "yes", "true") else 0}
        if isinstance(raw.get("phone"), (int, float)):
            digits = str(int(raw["phone"]))
            d["phone"] = digits if digits.startswith(("0", "1")) and len(digits) >= 10 else "0" + digits
        if not d["name"]:
            errors.append("Thiếu tên địa điểm")
        cat_raw = raw.get("category")
        d["category"] = cats.get(_norm_vi(cat_raw)) if cat_raw else None
        if not d["category"]:
            errors.append(f"Danh mục không hợp lệ: '{cat_raw or ''}'")
        lat, lng = parse_coords(raw.get("lat"), raw.get("lng"))
        if lat is None or lng is None:
            errors.append("Thiếu hoặc sai toạ độ")
        elif not (8 <= lat <= 24 and 102 <= lng <= 110):
            errors.append(f"Toạ độ ngoài Việt Nam ({lat}, {lng})")
        d["lat"], d["lng"] = lat, lng
        # phường
        ward_decl = widx.get(_norm_vi(raw.get("ward"))) if raw.get("ward") else None
        if raw.get("ward") and not ward_decl:
            warnings.append(f"Không nhận diện được phường '{raw.get('ward')}'")
        ward_geo = None
        if lat is not None and lng is not None and not errors:
            for slug, g in wgeoms:
                if point_in_geom(lng, lat, g):
                    ward_geo = slug
                    break
        if ward_decl and ward_geo and ward_decl != ward_geo:
            warnings.append(f"Toạ độ nằm trong ranh giới '{ward_geo}' khác phường khai báo '{ward_decl}'")
        d["ward_slug"] = ward_decl or ward_geo
        if not d["ward_slug"] and not errors:
            warnings.append("Toạ độ nằm ngoài các ranh giới phường đã số hoá")
        # ảnh
        images = []
        col_img = mapping.get("image")
        col_gal = mapping.get("gallery")
        col_vr = mapping.get("vr_url")
        vr_img = None
        # Excel365 in-cell
        for key_col in (col_img, col_gal, col_vr):
            if not key_col:
                continue
            ref = f"{get_column_letter(key_col)}{r}"
            b = cell365.get((ws.title, ref))
            if b:
                try:
                    if key_col == col_vr:
                        vr_img = store(b, "pano")
                    else:
                        images.append(store(b))
                except Exception:
                    warnings.append(f"Ảnh trong ô {ref} không đọc được")
            fv = ws_f.cell(r, key_col).value
            if isinstance(fv, str) and "DISPIMG" in fv.upper():
                m = re.search(r'DISPIMG\(\s*"([^"]+)"', fv, re.I)
                if m and m.group(1) in wps:
                    try:
                        if key_col == col_vr:
                            vr_img = store(wps[m.group(1)], "pano")
                        else:
                            images.append(store(wps[m.group(1)]))
                    except Exception:
                        warnings.append(f"Ảnh WPS trong ô {ref} không đọc được")
        # ảnh nổi
        for col, b in sorted(float_imgs.get(r, []), key=lambda t: (0 if t[0] == col_img else 1, t[0])):
            try:
                if col_vr and col == col_vr:
                    vr_img = store(b, "pano")
                else:
                    images.append(store(b))
            except Exception:
                warnings.append("Có ảnh chèn trong dòng không đọc được")
        # tên tệp / link
        for key in ("image", "gallery"):
            v = raw.get(key)
            if isinstance(v, str) and v.strip() and "DISPIMG" not in v.upper() and not v.startswith("#"):
                for ref in re.split(r"[;\n|]", v):
                    if ref.strip():
                        img, err = resolve_ref(ref)
                        if img:
                            images.append(img)
                        elif err:
                            warnings.append(err)
        d["images"] = images
        # VR360
        vr_type_raw = _norm_vi(raw.get("vr_type"))
        vr_ref = str(raw.get("vr_url") or "").strip()
        vr = None
        if vr_img:
            vr = {"type": "pano", "url": vr_img["url"], "thumb": vr_img["thumb"]}
        elif vr_ref and not vr_ref.startswith("#"):
            vt = VR_TYPES.get(vr_type_raw) or ("embed" if vr_ref.startswith("http") and not re.search(r"\.(jpe?g|png|webp)(\?|$)", vr_ref, re.I) else "pano")
            if vt == "video":
                vr = {"type": "video", "url": vr_ref}
            elif vr_ref.startswith("http"):
                vr = {"type": vt, "url": vr_ref}
            else:
                img, err = resolve_ref(vr_ref, "pano")
                if img:
                    vr = {"type": "pano", "url": img["url"], "thumb": img["thumb"]}
                else:
                    warnings.append(err or "Không đọc được VR360")
        d["vr360"] = vr
        # cập nhật hay tạo mới
        action = "create"
        target = None
        if d["code"]:
            ex_row = existing.get(d["code"])
            if ex_row:
                action, target = "update", ex_row["id"]
            else:
                warnings.append(f"Mã '{d['code']}' chưa tồn tại — sẽ tạo mới")
                d["code"] = None
        if action == "create" and lat is not None and lng is not None and d["name"]:
            for p in all_pois:
                if p["lat"] is not None and norm(p["name"]) == norm(d["name"]) and haversine_m(lat, lng, p["lat"], p["lng"]) < 60:
                    warnings.append(f"Có thể trùng với địa điểm {p['code']} đã có")
                    break
        rows.append({"row": r, "action": action, "poi_id": target, "data": d, "errors": errors, "warnings": warnings})
    return batch_id, rows


# ------------------------------------------------------------------ template
NAVY = "14346F"
GREEN = "17A673"


def build_template(sample_image_bytes=None):
    wb = openpyxl.Workbook()
    guide = wb.active
    guide.title = "HUONG_DAN"
    ws = wb.create_sheet("DIA_DIEM")
    lists = wb.create_sheet("DANH_MUC")
    thin = Side(style="thin", color="D5DCE8")

    # --- guide
    guide.column_dimensions["A"].width = 4
    guide.column_dimensions["B"].width = 30
    guide.column_dimensions["C"].width = 90
    guide["B2"] = "XANH24 – MAPS FOR LIFE"
    guide["B2"].font = Font(bold=True, size=18, color=NAVY)
    guide["B3"] = "Biểu mẫu nhập dữ liệu địa điểm địa phương"
    guide["B3"].font = Font(size=12, color="4B5B76")
    steps = [
        ("Bước 1", "Nhập mỗi địa điểm trên 1 dòng tại sheet DIA_DIEM (bắt đầu từ dòng 3, xoá 2 dòng ví dụ nếu muốn)."),
        ("Bước 2", "Cột có dấu * là bắt buộc: Tên, Danh mục, Vĩ độ, Kinh độ. Chọn Danh mục/Phường từ danh sách thả xuống."),
        ("Bước 3", "Ảnh: chèn ảnh trực tiếp vào ô 'Ảnh đại diện' (Insert > Picture > Place in Cell hoặc đặt ảnh nằm trong dòng), "
                   "hoặc ghi tên tệp ảnh rồi nén các ảnh thành .zip và tải lên cùng file Excel."),
        ("Bước 4", "VR360: ghi link tour 360 (Kuula, Matterport, 3DVista, Google Street View...) hoặc tên tệp ảnh 360 (tỉ lệ 2:1) trong .zip."),
        ("Bước 5", "Vào Dashboard > Nhập Excel, tải file lên, kiểm tra bản xem trước rồi 'Gửi phê duyệt'. "
                   "Admin S1 duyệt xong địa điểm mới hiển thị công khai."),
        ("Toạ độ", "Mở Google Maps, nhấn giữ vào vị trí để lấy '21.0285, 105.8542' — có thể dán nguyên chuỗi này vào cột Vĩ độ."),
        ("Cập nhật", "Muốn sửa địa điểm đã có: điền Mã địa điểm (X24-xxxxx) ở cột đầu, các cột khác là nội dung mới."),
    ]
    for i, (a, b) in enumerate(steps):
        guide.cell(5 + i, 2, a).font = Font(bold=True, color=GREEN)
        c = guide.cell(5 + i, 3, b)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        guide.row_dimensions[5 + i].height = 34
    guide.cell(5 + len(steps) + 1, 2, "Mô tả cột").font = Font(bold=True, color=NAVY, size=12)
    for i, (k, h, w, req, note) in enumerate(COLUMNS):
        guide.cell(7 + len(steps) + i, 2, h).font = Font(bold=req)
        guide.cell(7 + len(steps) + i, 3, note)

    # --- lists
    cats = q("SELECT name FROM categories WHERE active=1 ORDER BY sort")
    wards = q("SELECT name FROM wards ORDER BY name")
    lists["A1"], lists["B1"], lists["C1"] = "Danh mục", "Phường/Xã", "Loại VR360"
    for c in ("A1", "B1", "C1"):
        lists[c].font = Font(bold=True, color="FFFFFF")
        lists[c].fill = PatternFill("solid", fgColor=NAVY)
    for i, c in enumerate(cats):
        lists.cell(2 + i, 1, c["name"])
    for i, w in enumerate(wards):
        lists.cell(2 + i, 2, w["name"])
    for i, v in enumerate(["Ảnh 360", "Nhúng (iframe)", "Video 360"]):
        lists.cell(2 + i, 3, v)
    for col in "ABC":
        lists.column_dimensions[col].width = 30

    # --- data sheet
    ws["A1"] = "DỮ LIỆU ĐỊA ĐIỂM — Xanh24 Maps for Life (dòng 2 là tiêu đề, nhập từ dòng 3)"
    ws["A1"].font = Font(bold=True, color=NAVY, size=12)
    for i, (k, h, w, req, note) in enumerate(COLUMNS, start=1):
        c = ws.cell(2, i, h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY if req else "2A62B8")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[2].height = 34
    ws.freeze_panes = "C3"
    samples = [
        ["", "Ví dụ: Trụ sở UBND phường (xoá dòng này)", cats[0]["name"] if cats else "", "", "Số nhà, tên phố", 21.0301, 105.8503,
         "024 xxxx xxxx", "08:00–17:00 (T2–T6)", "", "Tiếp nhận và giải quyết thủ tục hành chính.", "", "", "", "", "hành chính, một cửa", "", "x"],
    ]
    for r, row in enumerate(samples, start=3):
        for i, v in enumerate(row, start=1):
            c = ws.cell(r, i, v)
            c.font = Font(italic=True, color="8A94A6")
    n_rows = 1000
    dv_cat = DataValidation(type="list", formula1=f"=DANH_MUC!$A$2:$A${1 + max(1, len(cats))}", allow_blank=True)
    dv_ward = DataValidation(type="list", formula1=f"=DANH_MUC!$B$2:$B${1 + max(1, len(wards))}", allow_blank=True)
    dv_vr = DataValidation(type="list", formula1="=DANH_MUC!$C$2:$C$4", allow_blank=True)
    for dv, key in ((dv_cat, "category"), (dv_ward, "ward"), (dv_vr, "vr_type")):
        col = get_column_letter(KEYS.index(key) + 1)
        dv.add(f"{col}3:{col}{n_rows}")
        ws.add_data_validation(dv)
    for r in range(3, 60):
        ws.row_dimensions[r].height = 60
    wb.active = 1
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
