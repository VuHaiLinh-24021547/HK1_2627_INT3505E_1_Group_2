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
    ![patch_success](/SOA4/img/patch/patch_success.png)
    * Missing bearer token, 401
    ![missing_token](/SOA4/img/patch/patch_401.png)
    * Forbidden from patch, 403
    ![forbidden](/SOA4/img/patch/patch_403.png)
    * Book not found, 404
    ![not_found](/SOA4/img/patch/patch_404.png)
    * Missing body, 400
    ![missing_body](/SOA4/img/patch/patch_400.png)
    * Violate a rule of a field data, 422
    ![price_less_0](/SOA4/img/patch/patch_422.png)
* **DELETE /books/{book_id}**
    * Delete success, 204
    ![status_code](/SOA4/img/delete/delete_204.png)
    ![no_body](/SOA4/img/delete/delete_success.png)
    
    * Missing bearer token, 401
    ![missing_token](/SOA4/img/delete/delete_401.png)
    * Forbidden from delete, 403
    ![forbidden](/SOA4/img/delete/delete_403.png)
    * Book not ofund, 404
    ![not_found](/SOA4/img/delete/delete_404.png)
    
**3.Try it out with Swagger UI**
* **Patch**
    * Success
    ![success](/SOA4/img/swagger_ui/patch/swagger_patch_200_1.png)
    ![success](/SOA4/img/swagger_ui/patch/swagger_patch_200_2.png)

    * Missing token
    ![missing_token](/SOA4/img/swagger_ui/patch/swagger_patch_401_1.png)
    ![missing_token](/SOA4/img/swagger_ui/patch/swagger_patch_401_2.png)
* **Delete**
    * Success
    ![success](/SOA4/img/swagger_ui/delete/swagger_delete_204.png)

    * Missing token
    ![missing_token](/SOA4/img/swagger_ui/delete/swagger_delete_401.png)