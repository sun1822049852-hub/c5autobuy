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


export function buildErrorDisplay(error) {
  const message = error instanceof Error ? error.message : String(error ?? "");

  return {
    details: getHttpErrorLines(error),
    message,
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
