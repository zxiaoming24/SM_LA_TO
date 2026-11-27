package com.dhi.wha.dto;


import lombok.Data;

@Data
public class UserAdminApplyDTO {
    private Boolean isNew;
    private Long id;
    private String username;
    private String avatar;
    private String email;
    private String remark;
    private Integer type;
}
