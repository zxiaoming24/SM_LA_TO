package com.dhi.wha.properties;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@Data
@ConfigurationProperties(prefix = "ppt.api")
public class PptApiProperties {
    private String host;
    private String appCode;
}