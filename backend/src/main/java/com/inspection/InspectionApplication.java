package com.inspection;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

/**
 * PCB 비전 검사 중앙 서버 메인 애플리케이션
 *
 * <p>역할:
 * - 라즈베리파이(엣지 디바이스)로부터 검사 결과 JSON을 수신
 * - MySQL에 검사 이력을 저장
 * - React 대시보드에 REST API 제공
 *
 * @EnableJpaAuditing: @CreatedDate 등 JPA Auditing 기능을 활성화하여
 *                     레코드 생성/수정 시각을 자동으로 기록한다.
 */
@SpringBootApplication
@EnableJpaAuditing
public class InspectionApplication {

    public static void main(String[] args) {
        SpringApplication.run(InspectionApplication.class, args);
    }
}
