package com.dhi.wha.dto;


import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserDTO {
    //用户名(注册的时候会有用户名)
    private String username;
    //邮箱
    private String email;
    //密码
    private String password;
    //邮箱验证码
    private Integer verificationCode;
}
