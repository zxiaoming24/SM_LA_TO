package com.dhi.wha.dto;


import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserInfoDTO {
    //用户id
    private Long id;
    //用户名
    private String username;
    //是否为新用户
    private Boolean isNew;
    //邮箱
    private String email;
    //专业
    private String major;
    //类型 0-管理员  1-学生  2-教师
    private Integer type;
    //头像
    private String avatar;
    //性别 0-女 1-男
    private Integer sex;
    //年龄
    private Integer age;
    //年级 1-大一 2-大二 3-大三 4-大四
    private Integer grade;
    //申请管理员理由
    private String remark;
}
