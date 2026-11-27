package com.dhi.wha.vo;


import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserVO {
    //用户id
    private Long id;
    //用户名
    private String username;
    //是否为新用户
    private Boolean isNew;
    //邮箱
    private String email;
    //头像
    private String avatar;
    //token
    private String token;
    // 身份 0-管理员  1-学生  2-教师
    private Integer type;
    //该用户是否构建画像
    private Integer isBuildProfile;
    //专业
    private String major;
    // 性别 0-女 1-男
    private Integer sex;
    // 年龄
    private Integer age;
    // 年级 1-大一 2-大二 3-大三 4-大四
    private Integer grade;
    // 判断是否需要指引
    private Integer tour;
}
