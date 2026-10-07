from flask import jsonify, request
from app import app  # Import app trực tiếp từ server/app.py

KEY = "smarthospital"

# Khai báo trực tiếp ở cấp module (không bọc trong hàm register_routes)
@app.route(f"/api/modules/{KEY}/directions", methods=["GET"], endpoint=f"mod_{KEY}_directions")
def get_hospital_directions():
    hospital = request.args.get("hospital", "pstw")
    
    # Dữ liệu phản hồi bản đồ chỉ đường
    response_data = {
        "status": "success",
        "hospital": hospital,
        "message": "Kết nối bản đồ thành công",
        "data": {
            "name": "Bệnh viện Phụ sản Trung ương",
            "address": "43 Tràng Thi, Hoàn Kiếm, Hà Nội",
            "coordinates": {
                "lat": 21.0268,
                "lng": 105.8475
            }
        }
    }
    return jsonify(response_data), 200