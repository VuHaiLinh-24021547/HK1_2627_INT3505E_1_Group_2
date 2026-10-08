* **API endpoints: status code**
    * GET /books: 200, 401 (Dinh Phuc Hung)
    * GET /books/<int:id>: 200, 404, 304, 401 (Dinh Phuc Hung)
    * POST /books: 201, 401 (Pham Quoc Anh)
    * PUT /books/<int:id>: 200, 404, 400, 401 (Pham Quoc Anh)
    * PATCH /books/<int:id>: 200, 404, 401 (Vu Hai Linh)
    * DELETE /books/<int:id>: 204, 404, 401 (Vu Hai Linh)
* **Requirements:**
    * Example for each schema
    * Write schema ref in components
    * Authorization for all endpoints(root level security only, don't need to write distinct authorization for each endpoints)
* **Notes:**
    * Use ref for every reponses of endpoints if they are long or they can be reused(for example, book's detail can be reused for GET, POST, PUT, PATCH)