# Week 12: api spec
Vu Hai Linh: write api specification(openapi.yaml)

# Week 13: backend
* Vu Hai Linh: 
    * crawl data from riot, data dragon to store in postgresSQL database
    * POST /oauth/tokens
    * POST /oauth/revocations
    * GET /regions/<region>/players/<gameName>/<tagLine>
    * POST /api/v1/players/<puuid>/sync-jobs

* Dinh Phuc Hung: 
    * train LightGBM model to evaluate win probability
    * GET /api/v1/players/<puuid>/matches
    * GET /api/v1/matches/<matchId>/review
    * GET /api/v1/static-catalogs/<patch>