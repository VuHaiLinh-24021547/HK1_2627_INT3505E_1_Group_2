* **API endpoints: status code**
    * GET /books: 200, 401, 403 (Dinh Phuc Hung)
    * GET /books/<int:id>: 200, 404, 304, 401, 403 (Dinh Phuc Hung)
    * POST /books: 201, 400, 401, 403 (Vu Hai Linh)
    * PUT /books/<int:id>: 200, 404, 400, 401, 403 (Vu Hai Linh)
    * PATCH /books/<int:id>: 200, 404, 401, 403, 400 (Vu Hai Linh)
    * DELETE /books/<int:id>: 204, 404, 401, 403 (Vu Hai Linh)
* **Requirements:**
    * Use OpenAPI 3.0
    * Example for each schema
    * Write schema ref in components
    * Authorization for all endpoints(root level security only, don't need to write distinct authorization for each endpoints)
    * Write Flask app for your endpoints
* **Notes:**
    * Use ref for every reponses of endpoints if they are long or they can be reused(for example, book's detail can be reused for GET, POST, PUT, PATCH)
    * Pull code to your own branch. Do not push to main branch