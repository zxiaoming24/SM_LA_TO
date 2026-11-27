package com.dhi.wha.dto;

import lombok.Data;

@Data
public class StudyBuddyAcceptDTO {
    private String userId;
    private String companionId;
    private Boolean accept;
}
