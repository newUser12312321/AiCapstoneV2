package com.inspection.domain.enums;

/**
 * 검사 최종 판정 결과 열거형
 *
 * <p>PASS: 피듀셜 마크 정렬 및 결함 탐지 모두 이상 없음
 * <p>FAIL: 정렬 오차 초과 또는 결함(단선/까짐) 탐지됨
 *
 * <p>DB 저장 시 EnumType.STRING으로 "PASS" / "FAIL" 문자열로 저장하여
 * 가독성과 마이그레이션 안전성을 높인다.
 */
public enum InspectionResult {

    /** 합격: 모든 검사 항목 통과 */
    PASS,

    /** 불합격: 하나 이상의 검사 항목 실패 */
    FAIL
}
