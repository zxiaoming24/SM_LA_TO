package com.dhi.wha.constant;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ClickRecord {
    /**
     * 资源类型，如 VIDEO、MIND_MAP、PPT 等
     */
    String resourceType();

    /**
     * 方法中哪个参数名代表资源ID
     */
    String resourceIdParam() default "id";
}
