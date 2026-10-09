# HK1_2627_INT3505E_1_Group_2

**1.Endpoints**
* GET /books
* GET /books/{book_id}
* POST /books
* PUT /books/{book_id}
* PATCH /books/{book_id}
* DELETE /books/{book_id}
**2.Reponses for each endpoint**
* **GET /books**
* **GET /books/{book_id}**
* **POST /books**
* **PUT /books/{book_id}**
* **PATCH /books/{book_id}**
    * Patch success, 200
    ![patch_success](/img/patch/patch_success.png)
    * Missing bearer token, 401
    ![missing_token](/img/patch/patch_401.png)
    * Forbidden from patch, 403
    ![forbidden](/img/patch/patch_403.png)
    * Book not found, 404
    ![not_found](/img/patch/patch_404.png)
    * Missing body, 400
    ![missing_body](/img/patch/patch_400.png)
    * Violate a rule of a field data, 422
    ![price_less_0](/img/patch/patch_422.png)
* **DELETE /books/{book_id}**
    * Delete success, 204
    ![status_code](/img/delete/delete_204.png)
    ![no_body](/img/delete/delete_success.png)
    * Missing bearer token, 401
    ![missing_token](/img/delete/delete_401.png)
    * Forbidden from delete, 403
    ![forbidden](/img/delete/delete_403.png)
    * Book not ofund, 404
    ![not_found](/img/delete/delete_404.png)