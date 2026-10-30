"""Saved public places for USER accounts."""

from flask import Blueprint, g, jsonify, request

from cms import authenticate, error, role
from db import ex, now, q


discovery = Blueprint("user_discovery", __name__)


def user_only():
    return role("USER")


@discovery.route("/api/user/saved", methods=["GET"])
@authenticate
def saved_places():
    if not user_only():
        return error("Không có quyền", 403)
    rows = q("SELECT s.poi_id FROM user_saved_places s JOIN pois p ON p.id=s.poi_id "
             "WHERE s.account_id=? AND p.status='published' AND NOT EXISTS "
             "(SELECT 1 FROM cms_pins cp WHERE cp.poi_id=p.id AND "
             "(cp.active=0 OR cp.approved_at IS NULL OR cp.expires_at IS NULL OR cp.expires_at<=?)) "
             "ORDER BY s.created_at DESC, s.poi_id DESC", (g.cms_user["id"], now()))
    return jsonify(items=[row["poi_id"] for row in rows])


@discovery.route("/api/user/saved/<int:poi_id>", methods=["POST", "DELETE"])
@authenticate
def save_place(poi_id):
    if not user_only():
        return error("Không có quyền", 403)
    if request.method == "DELETE":
        ex("DELETE FROM user_saved_places WHERE account_id=? AND poi_id=?", (g.cms_user["id"], poi_id))
        return jsonify(saved=False)
    visible = q("SELECT 1 FROM pois p WHERE p.id=? AND p.status='published' AND NOT EXISTS "
                "(SELECT 1 FROM cms_pins cp WHERE cp.poi_id=p.id AND "
                "(cp.active=0 OR cp.approved_at IS NULL OR cp.expires_at IS NULL OR cp.expires_at<=?))",
                (poi_id, now()), one=True)
    if not visible:
        return error("Địa điểm không còn hiển thị", 404)
    ex("INSERT INTO user_saved_places(account_id,poi_id,created_at) VALUES(?,?,?) "
       "ON CONFLICT(account_id,poi_id) DO NOTHING", (g.cms_user["id"], poi_id, now()))
    return jsonify(saved=True)
