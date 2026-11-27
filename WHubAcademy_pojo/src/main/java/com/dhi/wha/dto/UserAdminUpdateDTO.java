package com.dhi.wha.dto;

import lombok.Data;

@Data
public class UserAdminUpdateDTO {
    private Long userId;
    private String avatar;
    private String username;
    private Integer sex;
    private Integer grade;
    private String major;
}
