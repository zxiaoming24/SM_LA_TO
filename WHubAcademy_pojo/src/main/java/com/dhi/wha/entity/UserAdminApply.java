package com.dhi.wha.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("user_admin_apply")
public class UserAdminApply {
    /**
     * id
     */
    @TableId(value = "id", type = IdType.AUTO)
    private Long id;
    /**
     * 申请人id
     */
    private Long userId;
    /**
     * 申请人姓名
     */
    @TableField("user_name")
    private String user_name;
    /**
     * 申请原因
     */
    private String remark;
}
