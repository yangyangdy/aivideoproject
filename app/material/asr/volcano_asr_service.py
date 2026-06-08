from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx

from app.material.asr.payload_builder import normalize_asr_result
from app.material.config import MaterialSettings
from app.material.domain.asr_models import AsrQueryResult, AsrRecognizeResult, AsrSubmitResult
from app.material.logging_utils import log_json, mask_headers, truncate_text

logger = logging.getLogger(__name__)

STATUS_SUCCESS = "20000000"
STATUS_PENDING = "20000001"
STATUS_PROCESSING = "20000002"


class VolcanoAsrService:
    """Volcano Engine ASR v3 bigmodel service with word-level utterances."""

    def __init__(self, settings: MaterialSettings):
        self.settings = settings

    def submit_task(
        self,
        audio_url: str,
        *,
        uid: int = 0,
        audio_format: str | None = None,
        callback_url: str | None = None,
        api_key: str | None = None,
        resource_id: str | None = None,
    ) -> AsrSubmitResult:
        logger.info("VolcanoAsrService.submit_task audio_url=%s", audio_url)
        try:
            task_id = str(uuid.uuid4())
            headers = self._build_headers(task_id, api_key=api_key, resource_id=resource_id, for_submit=True)
            request_body = self._build_submit_body(
                audio_url,
                uid=uid,
                audio_format=audio_format,
                callback_url=callback_url,
            )

            response = self._send_post(self.settings.asr_submit_url, request_body, headers)
            status_code = response["headers"].get("X-Api-Status-Code", "")
            status_message = response["headers"].get("X-Api-Message", "")
            x_tt_logid = response["headers"].get("X-Tt-Logid", "")

            if status_code == STATUS_SUCCESS:
                logger.info("ASR submit ok task_id=%s x_tt_logid=%s", task_id, x_tt_logid)
                return AsrSubmitResult(success=True, task_id=task_id, x_tt_logid=x_tt_logid)

            error = f"ASR提交失败: {status_message} (code: {status_code})"
            logger.error("ASR submit failed: %s", error)
            return AsrSubmitResult(success=False, task_id=task_id, error=error)
        except ValueError as exc:
            logger.error("ASR submit failed: %s", exc)
            return AsrSubmitResult(success=False, error=str(exc))
        except Exception as exc:
            logger.exception("ASR submit exception")
            return AsrSubmitResult(success=False, error=str(exc))

    def query_task(
        self,
        task_id: str,
        *,
        x_tt_logid: str = "",
        api_key: str | None = None,
        resource_id: str | None = None,
    ) -> AsrQueryResult:
        logger.info("VolcanoAsrService.query_task task_id=%s", task_id)
        try:
            headers = self._build_headers(task_id, api_key=api_key, resource_id=resource_id, for_submit=False)
            response = self._send_post(self.settings.asr_query_url, {}, headers)
            status_code = response["headers"].get("X-Api-Status-Code", "")
            status_message = response["headers"].get("X-Api-Message", "")
            body = response.get("body") or {}

            if status_code == STATUS_SUCCESS and self._is_recognition_ready(body):
                normalized = normalize_asr_result(body)
                word_count = sum(len(item.get("words") or []) for item in normalized.get("utterances") or [])
                logger.info(
                    "ASR query completed task_id=%s utterance_count=%s word_count=%s",
                    task_id,
                    len(normalized.get("utterances") or []),
                    word_count,
                )
                return AsrQueryResult(success=True, status="completed", data=body)
            if status_code in {STATUS_SUCCESS, STATUS_PENDING, STATUS_PROCESSING}:
                return AsrQueryResult(
                    success=True,
                    status="processing" if status_code == STATUS_SUCCESS else "pending",
                )

            error = status_message or f"ASR识别失败，错误码：{status_code}"
            return AsrQueryResult(success=False, status="failed", error=error)
        except ValueError as exc:
            logger.error("ASR query failed: %s", exc)
            return AsrQueryResult(success=False, status="failed", error=str(exc))
        except Exception as exc:
            logger.exception("ASR query exception")
            return AsrQueryResult(success=False, status="failed", error=str(exc))

    def recognize(
        self,
        audio_url: str,
        *,
        uid: int = 0,
        audio_format: str | None = None,
        callback_url: str | None = None,
        api_key: str | None = None,
        resource_id: str | None = None,
        poll_interval_seconds: float | None = None,
        poll_max_attempts: int | None = None,
    ) -> AsrRecognizeResult:
        logger.info("VolcanoAsrService.recognize start audio_url=%s uid=%s", audio_url, uid)
        submit = self.submit_task(
            audio_url,
            uid=uid,
            audio_format=audio_format,
            callback_url=callback_url,
            api_key=api_key,
            resource_id=resource_id,
        )
        if not submit.success:
            return AsrRecognizeResult(success=False, task_id=submit.task_id, error=submit.error)

        interval = poll_interval_seconds if poll_interval_seconds is not None else self.settings.asr_poll_interval_seconds
        max_attempts = poll_max_attempts if poll_max_attempts is not None else self.settings.asr_poll_max_attempts

        for _ in range(max_attempts):
            query = self.query_task(
                submit.task_id,
                x_tt_logid=submit.x_tt_logid,
                api_key=api_key,
                resource_id=resource_id,
            )
            if not query.success:
                return AsrRecognizeResult(
                    success=False,
                    task_id=submit.task_id,
                    x_tt_logid=submit.x_tt_logid,
                    error=query.error,
                )
            if query.status == "completed":
                normalized = normalize_asr_result(query.data)
                logger.info(
                    "VolcanoAsrService.recognize completed task_id=%s text_preview=%s word_count=%s",
                    submit.task_id,
                    truncate_text(str(normalized.get("text") or ""), 120),
                    sum(len(item.get("words") or []) for item in normalized.get("utterances") or []),
                )
                return AsrRecognizeResult(
                    success=True,
                    task_id=submit.task_id,
                    x_tt_logid=submit.x_tt_logid,
                    data=query.data,
                )
            if query.status in ("pending", "processing"):
                time.sleep(interval)
                continue
            return AsrRecognizeResult(
                success=False,
                task_id=submit.task_id,
                x_tt_logid=submit.x_tt_logid,
                error=query.error or "ASR task failed",
            )

        return AsrRecognizeResult(
            success=False,
            task_id=submit.task_id,
            x_tt_logid=submit.x_tt_logid,
            error=f"ASR task timed out after {max_attempts} poll attempts",
        )

    def _build_headers(
        self,
        request_id: str,
        *,
        api_key: str | None,
        resource_id: str | None,
        for_submit: bool,
    ) -> dict[str, str]:
        headers = {
            "X-Api-Resource-Id": resource_id or self.settings.asr_resource_id,
            "X-Api-Request-Id": request_id,
        }

        app_id = self.settings.asr_app_id.strip()
        access_token = self.settings.asr_access_token.strip()
        if app_id and access_token:
            headers["X-Api-App-Key"] = app_id
            headers["X-Api-Access-Key"] = access_token
            return headers

        key = (api_key or self.settings.asr_api_key).strip()
        if not key:
            raise ValueError("ASR credentials not configured: set ASR_APP_ID+ASR_ACCESS_TOKEN or ASR_API_KEY")
        if key.startswith("your_") or key == "your_api_key_here":
            raise ValueError("ASR_API_KEY is still placeholder, please set a real key in .env")

        headers["X-Api-Key"] = key
        if for_submit:
            headers["X-Api-Sequence"] = "-1"
        return headers

    def _build_submit_body(
        self,
        audio_url: str,
        *,
        uid: int,
        audio_format: str | None,
        callback_url: str | None,
    ) -> dict[str, Any]:
        request_body: dict[str, Any] = {
            "user": {"uid": str(uid)},
            "audio": {
                "url": audio_url,
                "format": audio_format or infer_audio_format(audio_url) or self.settings.asr_audio_format,
            },
            "request": {
                "model_name": self.settings.asr_model_name,
                "enable_itn": self.settings.asr_enable_itn,
                "enable_punc": self.settings.asr_enable_punc,
                "show_utterances": self.settings.asr_show_utterances,
            },
        }
        if callback_url:
            request_body["request"]["callback"] = callback_url
        return request_body

    @staticmethod
    def _is_recognition_ready(body: dict[str, Any]) -> bool:
        result = body.get("result") or {}
        return bool(str(result.get("text") or "").strip())

    def _send_post(self, url: str, data: dict[str, Any] | None, headers: dict[str, str]) -> dict[str, Any]:
        body = json.dumps(data if data is not None else {}, ensure_ascii=False)
        timeout = self.settings.asr_timeout_seconds
        safe_headers = mask_headers(headers)
        log_json(logger, logging.INFO, f"ASR HTTP request url={url} headers", safe_headers)
        log_json(logger, logging.INFO, f"ASR HTTP request url={url} body", data or {})

        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, content=body, headers=headers)

        if response.status_code >= 400:
            logger.error(
                "ASR HTTP error url=%s status=%s body=%s",
                url,
                response.status_code,
                truncate_text(response.text, 800),
            )
            raise ValueError(f"HTTP错误：{response.status_code}, 响应：{response.text[:800]}")

        parsed_body: dict[str, Any] = {}
        if response.text:
            try:
                loaded = response.json()
                if isinstance(loaded, dict):
                    parsed_body = loaded
            except json.JSONDecodeError:
                parsed_body = {}

        resp_headers = {
            "X-Api-Status-Code": response.headers.get("x-api-status-code", ""),
            "X-Api-Message": response.headers.get("x-api-message", ""),
            "X-Tt-Logid": response.headers.get("x-tt-logid", ""),
        }
        log_json(logger, logging.INFO, f"ASR HTTP response url={url} headers", resp_headers)
        log_json(logger, logging.INFO, f"ASR HTTP response url={url} body", parsed_body)
        return {"headers": resp_headers, "body": parsed_body}


def infer_audio_format(audio_url: str) -> str:
    path = urlparse(audio_url).path
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext or ""
