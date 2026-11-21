from flask import jsonify

from ..auth.jwt_auth import require_scopes
from ..services import player_service, review_service
from . import api_v1
from .request_utils import query_params
from .schemas import MatchListQuery


@api_v1.get("/regions/<region>/players/<game_name>/<tag_line>")
@require_scopes("players:read")
def get_player(region, game_name, tag_line):
    player = player_service.get_or_fetch_player(region, game_name, tag_line)
    return jsonify(player_service.serialize_player(player)), 200


@api_v1.get("/players/<puuid>/matches")
@require_scopes("matches:read")
def list_player_matches(puuid):
    q = query_params(MatchListQuery)
    body = review_service.list_matches(
        puuid, limit=q.limit, cursor=q.cursor, queue_id=q.queueId, champion_id=q.championId
    )
    return jsonify(body), 200
