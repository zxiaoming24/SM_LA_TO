package com.dhi.wha.vo;

import lombok.Data;

import java.time.LocalDateTime;

@Data
public class UserListVO {
    private Long id;
    private String username;
    private Integer type;
    private String avatar;
    private String email;
    private Integer sex;
    private LocalDateTime createTime;
    private Integer grade;
    private String major;
}
