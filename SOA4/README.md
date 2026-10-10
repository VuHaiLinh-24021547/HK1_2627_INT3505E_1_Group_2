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
    * Post success, 201
    ![post_success](/SOA4/img/post/post_201.png)
    * Missing bearer token, 401
    ![missing_token](/SOA4/img/post/post_401.png)
    * Forbidden from post, 403
    ![forbidden](/SOA4/img/post/post_403.png)
    * Missing body, 400
    ![missing_body](/SOA4/img/post/post_400.png)
    * Violate a rule of a field data or missing field, 422
    ![something](/SOA4/img/post/post_422.png)
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
* **GET**
    * Success

    * Missing token

* **GET with id**
    * Success

    * Missing token
    
* **POST**
    * Success
    ![success](/SOA4/img/swagger_ui/post/swagger_post_201_1.png)
    ![success](/SOA4/img/swagger_ui/post/swagger_post_201_2.png)

    * Missing token
    ![missing_token](/SOA4/img/swagger_ui/post/swagger_post_401_1.png)
    ![missing_token](/SOA4/img/swagger_ui/post/swagger_post_401_2.png)
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

** 4. 2 Quyết định Thiết kế Khó nhất**
* **Phân định ranh giới giữa HTTP Status Code 400 và 422 trong thao tác PATCH**
    * Phương thức PATCH được sử dụng để cập nhật một phần thông tin tài nguyên sách (title, author, price), PATCH chấp nhận body chứa một hoặc nhiều trường dữ liệu tùy chọn. Thách thức đặt ra là làm thế nào để phản hồi lỗi chính xác cho client khi dữ liệu gửi lên không hợp lệ.
    * Hướng giải quyết: trả về 400 Bad Request khi client gọi PATCH nhưng không gửi JSON body hoặc body rỗng, trả vef Unprocessable Entity khi JSON body có cú pháp hợp lệ nhưng giá trị truyền vào vi phạm quy tắc nghiệp vụ(price < 0 hoặc sai kiểu dữ liệu)
    * Cách phân định này giúp client lập tức biết nguyên nhân lỗi đến từ cú pháp hay từ dữ liệu nhập không thỏa mãn điều kiện logic
* **Phân biệt 401 Unauthorized vs 403 Forbidden và nhúng Role vào Stateless JWT Payload**
    * Hệ thống cần phân quyền truy cập:
        * Người dùng có vai trò viewer chỉ có quyền xem thông tin.
        * Người dùng có vai trò admin mới được phép chỉnh sửa (PATCH) hoặc xóa (DELETE) sách.
    * Phân biệt chính xác hai trạng thái lỗi xác thực (Authentication) và phân quyền (Authorization), đồng thời kiểm tra quyền hạn một cách hiệu quả mà không làm giảm hiệu năng server.
    * Hướng giải quyết: Nhúng role trực tiếp vào Payload của JWT Token khi đăng nhập và kiểm tra phân quyền bằng Custom Decorator @role_required.
        * Payload của JWT: Khi cấp Token tại /login/admin hoặc /login/viewer, thông tin role được đưa trực tiếp vào payload: {"user": "admin", "role": "admin"}. Chữ ký JWT (Signature) đảm bảo Token này không thể bị sửa đổi bởi phía Client.
        * Phân định rõ 2 Status Code bảo mật: 401 Unauthorized: Trả về khi request thiếu Token, Token hết hạn hoặc Token bị sai định dạng / sai chữ ký. Đây là lỗi ở khâu xác minh danh tính. 403 Forbidden: Trả về khi Token hoàn toàn hợp lệ, danh tính người dùng đã được xác nhận, nhưng role của người dùng (ví dụ: viewer) không có quyền thực hiện hành động PATCH hay DELETE. Đây là lỗi ở khâu phân quyền hạn.
    * Quyết định này giúp giảm thiểu việc truy vấn cơ sở dữ liệu không cần thiết, tối ưu hóa tốc độ xử lý request và đảm bảo chuẩn mực thiết kế RESTful Security.