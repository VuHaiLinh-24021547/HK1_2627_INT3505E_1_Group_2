from flask import jsonify

from ..auth.jwt_auth import require_scopes
from ..services import review_service
from . import api_v1
from .errors import ApiError
from .request_utils import query_params
from .schemas import MATCH_ID_RE, ReviewQuery


@api_v1.get("/matches/<match_id>/review")
@require_scopes("matches:read")
def get_match_review(match_id):
    if not MATCH_ID_RE.match(match_id):
        raise ApiError(400, "INVALID_MATCH_ID", "matchId must look like 'VN2_492817261'.")
    q = query_params(ReviewQuery)
    match_id = match_id.split("_", 1)[0].upper() + "_" + match_id.split("_", 1)[1]
    return jsonify(review_service.get_review(match_id, region=q.region, focus_puuid=q.focusPuuid)), 200
