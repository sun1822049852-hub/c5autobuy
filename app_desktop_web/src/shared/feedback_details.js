import { resolveProgramAccessMessage } from "../program_access/program_access_messages.js";


function stringifyDetailValue(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  if (typeof value === "string") {
    return value;
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function tryParseJsonPayload(rawValue) {
  if (typeof rawValue !== "string" || !rawValue.trim()) {
    return null;
  }

  try {
    return JSON.parse(rawValue);
  } catch {
    return null;
  }
}

function extractPayloadMessage(payload) {
  if (!payload || typeof payload !== "object") {
    return "";
  }

  const detail = payload.detail && typeof payload.detail === "object"
    ? payload.detail
    : payload;
  const code = typeof detail.code === "string"
    ? detail.code
    : (typeof payload.error_code === "string" ? payload.error_code : "");

  if (typeof detail.message === "string" && detail.message.trim()) {
    return resolveProgramAccessMessage({
      code,
      message: detail.message.trim(),
    }) || detail.message.trim();
  }

  if (typeof payload.message === "string" && payload.message.trim()) {
    return resolveProgramAccessMessage({
      code,
      message: payload.message.trim(),
    }) || payload.message.trim();
  }

  if (typeof detail.error === "string" && detail.error.trim()) {
    return detail.error.trim();
  }

  return "";
}

function extractMessageFromValue(value) {
  if (value === null || value === undefined) {
    return "";
  }

  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return "";
    }

    const payload = tryParseJsonPayload(trimmed);
    return extractPayloadMessage(payload) || trimmed;
  }

  if (typeof value === "object") {
    return extractPayloadMessage(value) || stringifyDetailValue(value);
  }

  return String(value);
}

export function getUserFacingErrorMessage(error) {
  if (error instanceof Error) {
    const responseMessage = extractMessageFromValue(error.responseText);
    if (responseMessage) {
      return responseMessage;
    }

    const directMessage = extractMessageFromValue(error.message);
    if (directMessage) {
      return directMessage;
    }

    return "操作失败，请稍后重试。";
  }

  return extractMessageFromValue(error) || "操作失败，请稍后重试。";
}


export function buildErrorDisplay(error) {
  return {
    details: [],
    message: getUserFacingErrorMessage(error),
  };
}


export function getHttpErrorLines(error) {
  if (!(error instanceof Error)) {
    return [];
  }

  const lines = [];

  if (error.status) {
    lines.push(`HTTP ${error.status}`);
  }

  if (error.method && error.path) {
    lines.push(`${String(error.method).toUpperCase()} ${error.path}`);
  }

  if (error.responseText) {
    lines.push(`原始返回：${stringifyDetailValue(error.responseText)}`);
  }

  return lines;
}


export function getEventDetailLines(event = {}) {
  const lines = [];
  const httpStatus = event.http_status ?? event.status_code ?? event.response_status;
  const method = event.request_method ?? event.method;
  const path = event.request_path ?? event.path ?? event.url_path;
  const rawStatus = event.raw_status ?? event.rawState;
  const error = event.error ?? event.error_message;
  const requestBody = event.request_body;
  const responseText = event.response_text ?? event.raw_response ?? event.response_body;

  if (httpStatus) {
    lines.push(`HTTP ${httpStatus}`);
  }

  if (method && path) {
    lines.push(`${String(method).toUpperCase()} ${path}`);
  }

  if (rawStatus) {
    lines.push(`原始状态：${stringifyDetailValue(rawStatus)}`);
  }

  if (error) {
    lines.push(`错误：${stringifyDetailValue(error)}`);
  }

  if (requestBody) {
    lines.push(`请求体：${stringifyDetailValue(requestBody)}`);
  }

  if (responseText) {
    lines.push(`原始返回：${stringifyDetailValue(responseText)}`);
  }

  if (event.payload) {
    lines.push(`payload：${stringifyDetailValue(event.payload)}`);
  }

  if (event.result) {
    lines.push(`result：${stringifyDetailValue(event.result)}`);
  }

  return lines;
}
