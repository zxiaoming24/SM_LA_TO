package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("user")
public class User implements Serializable {
    // 用户id
    @TableId(type = IdType.AUTO)
    private Long id;
    // 用户名
    private String username;
    // 手机号
    private String phone;
    // 邮箱
    private String email;
    //是否为新用户
    @TableField(value = "is_new")
    private Boolean isNew;
    //是否已经构建画像
    @TableField(value = "is_build_profile")
    private Integer isBuildProfile;
    //专业
    private String major;
    // 密码
    private String password;
    // 创建时间
    private LocalDateTime createTime;
    // 头像
    private String avatar;
    // 身份 -3-申请成为管理员 -2-新注册用户 0-管理员  1-学生 -1-全部
    private Integer type;
    // 性别 0-女 1-男
    private Integer sex;
    // 年龄
    private Integer age;
    // 年级 1-大一 2-大二 3-大三 4-大四
    private Integer grade;
    // 判断是否需要新手指引（0-不需要 1-需要）
    private Integer tour;
}