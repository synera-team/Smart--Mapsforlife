"""Kiểm thử đọc ảnh nhúng trong ô: WPS (DISPIMG) và Excel 365 (Place in Cell / richData)."""
import io, os, re, sys, zipfile, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp(); os.environ["XANH24_DATA_DIR"] = tmp; os.environ["XANH24_DB"] = os.path.join(tmp, "t.db")
sys.path.insert(0, os.path.join(ROOT, "server"))
import db; db.UPLOAD_DIR = os.path.join(tmp, "up")
import media; media.UPLOAD_DIR = db.UPLOAD_DIR
db.init_db()
from seed import seed_all; seed_all(log=lambda *a: None)
import importer, openpyxl
from PIL import Image

def png(c):
    b = io.BytesIO(); Image.new("RGB", (80, 60), c).save(b, "PNG"); return b.getvalue()

def base_book(cell_formula=None):
    wb = openpyxl.load_workbook(io.BytesIO(importer.build_template()))
    ws = wb["DIA_DIEM"]
    ws.append(["", "Điểm có ảnh trong ô", "Y tế", "", "", 21.03, 105.85, "", "", "", "", cell_formula or "X"])
    b = io.BytesIO(); wb.save(b); return b.getvalue()

def rewrite(data, add, patch_sheet=None):
    src = zipfile.ZipFile(io.BytesIO(data)); out = io.BytesIO(); z = zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED)
    sheet = None
    for n in src.namelist():
        d = src.read(n)
        if n == "[Content_Types].xml":
            d = d.replace(b"</Types>", b'<Default Extension="png" ContentType="image/png"/></Types>') if b'Extension="png"' not in d else d
        if patch_sheet and n.startswith("xl/worksheets/sheet") and b"Ghi" not in d and b"L4" in d:
            d = patch_sheet(d); sheet = n
        z.writestr(n, d)
    for n, d in add.items(): z.writestr(n, d)
    z.close(); return out.getvalue(), sheet

# ---- WPS
x = base_book('=_xlfn.DISPIMG("ID_TEST1",1)')
cellimages = b'''<?xml version="1.0" encoding="UTF-8"?><etc:cellImages xmlns:etc="http://www.wps.cn/officeDocument/2017/etCustomData" xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><etc:cellImage><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="2" name="ID_TEST1"/><xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill><a:blip r:embed="rId1"/></xdr:blipFill></xdr:pic></etc:cellImage></etc:cellImages>'''
rels = b'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/wps1.png"/></Relationships>'
x2, _ = rewrite(x, {"xl/cellimages.xml": cellimages, "xl/_rels/cellimages.xml.rels": rels, "xl/media/wps1.png": png((255, 0, 0))})
_, rows = importer.parse_workbook(x2)
assert len(rows) == 1 and len(rows[0]["data"]["images"]) == 1, rows
print("  ✓ WPS DISPIMG: nhận 1 ảnh")

# ---- Excel 365 richData
x = base_book("X")
def patch(d):
    return re.sub(rb'<c r="L4"([^>]*)t="\w+"([^>]*)>.*?</c>', rb'<c r="L4" t="e" vm="1"><v>#VALUE!</v></c>', d, flags=re.S)
meta = b'''<?xml version="1.0" encoding="UTF-8"?><metadata xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:xlrd="http://schemas.microsoft.com/office/spreadsheetml/2017/richdata"><metadataTypes count="1"><metadataType name="XLRICHVALUE" minSupportedVersion="120000"/></metadataTypes><futureMetadata name="XLRICHVALUE" count="1"><bk><extLst><ext uri="{3e2802c4-a4d2-4d8b-9148-e3be6c30e623}"><xlrd:rvb i="0"/></ext></extLst></bk></futureMetadata><valueMetadata count="1"><bk><rc t="1" v="0"/></bk></valueMetadata></metadata>'''
rv = b'<?xml version="1.0" encoding="UTF-8"?><rvData xmlns="http://schemas.microsoft.com/office/spreadsheetml/2017/richdata" count="1"><rv s="0"><v>0</v><v>5</v></rv></rvData>'
rvrel = b'<?xml version="1.0" encoding="UTF-8"?><richValueRels xmlns="http://schemas.microsoft.com/office/spreadsheetml/2022/richvaluerel" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><rel r:id="rId1"/></richValueRels>'
rvrels = b'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/rich1.png"/></Relationships>'
x2, sheet = rewrite(x, {"xl/metadata.xml": meta, "xl/richData/rdrichvalue.xml": rv, "xl/richData/richValueRel.xml": rvrel, "xl/richData/_rels/richValueRel.xml.rels": rvrels, "xl/media/rich1.png": png((0, 0, 255))}, patch)
imgs = importer.excel365_cell_images(x2)
assert len(imgs) == 1, imgs.keys()
print("  ✓ Excel 365 Place-in-Cell: nhận", list(imgs.keys()))
print("ĐẠT")
