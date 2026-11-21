import hashlib

from flask import Response, json, request

from ..auth.jwt_auth import require_scopes
from ..services import ddragon_service
from . import api_v1
from .errors import ApiError
from .request_utils import query_params
from .schemas import CatalogQuery


@api_v1.get("/static-catalogs/<patch>")
@require_scopes("static:read")
def get_static_catalog(patch):
    if patch != "latest" and not ddragon_service.PATCH_RE.match(patch):
        raise ApiError(400, "INVALID_PATCH", "patch must be 'latest' or a version like '16.23' / '16.23.1'.")
    q = query_params(CatalogQuery)
    catalog = ddragon_service.get_catalog(patch, q.lang)
    if catalog is None:
        raise ApiError(404, "PATCH_NOT_FOUND", f"No static catalog for patch '{patch}' and lang '{q.lang}'.")

    body = json.dumps(catalog)
    etag = '"' + hashlib.sha256(body.encode()).hexdigest()[:32] + '"'
    headers = {"Cache-Control": "public, max-age=86400", "ETag": etag, "Vary": "Authorization"}
    if etag in request.headers.get("If-None-Match", ""):
        return Response(status=304, headers=headers)
    return Response(body, status=200, mimetype="application/json", headers=headers)
