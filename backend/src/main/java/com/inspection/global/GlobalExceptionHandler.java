package com.inspection.global;

import lombok.extern.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 전역 예외 처리기
 *
 * <p>컨트롤러에서 발생하는 예외를 한 곳에서 처리하여
 * 일관된 에러 응답 형식을 제공한다.
 *
 * @RestControllerAdvice: 모든 @RestController에 적용되는 AOP 기반 예외 처리
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * Bean Validation 실패 처리 (400 Bad Request)
     *
     * <p>@Valid 검증 실패 시 Spring이 던지는 MethodArgumentNotValidException을 잡아
     * 어떤 필드가 왜 실패했는지 상세히 반환한다.
     *
     * <p>예시 응답:
     * {
     *   "timestamp": "2026-03-31T14:30:00",
     *   "status": 400,
     *   "message": "입력값 검증 실패",
     *   "errors": { "result": "결과는 PASS 또는 FAIL이어야 합니다." }
     * }
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidationException(
            MethodArgumentNotValidException ex) {

        // 필드별 에러 메시지 수집
        Map<String, String> fieldErrors = new HashMap<>();
        ex.getBindingResult().getAllErrors().forEach(error -> {
            String fieldName = ((FieldError) error).getField();
            fieldErrors.put(fieldName, error.getDefaultMessage());
        });

        log.warn("[유효성 검사 실패] {}", fieldErrors);

        return ResponseEntity.badRequest().body(Map.of(
                "timestamp", LocalDateTime.now().toString(),
                "status",    400,
                "message",   "입력값 검증 실패",
                "errors",    fieldErrors
        ));
    }

    /**
     * 리소스 미존재 처리 (404 Not Found)
     *
     * <p>서비스 레이어에서 던지는 IllegalArgumentException을 404로 변환한다.
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleNotFoundException(
            IllegalArgumentException ex) {

        log.warn("[리소스 없음] {}", ex.getMessage());

        return ResponseEntity.status(404).body(Map.of(
                "timestamp", LocalDateTime.now().toString(),
                "status",    404,
                "message",   ex.getMessage()
        ));
    }

    /**
     * 그 외 처리되지 않은 예외 (500 Internal Server Error)
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleGenericException(Exception ex) {
        log.error("[서버 내부 오류]", ex);

        return ResponseEntity.internalServerError().body(Map.of(
                "timestamp", LocalDateTime.now().toString(),
                "status",    500,
                "message",   "서버 내부 오류가 발생했습니다."
        ));
    }
}
