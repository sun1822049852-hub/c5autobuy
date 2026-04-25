import React from "react";

import { logRendererDiagnostic } from "./renderer_diagnostics.js";


const FALLBACK_CONTAINER_STYLE = {
  alignItems: "center",
  background: "linear-gradient(180deg, #161a22 0%, #0f1218 100%)",
  color: "#f3efe6",
  display: "flex",
  justifyContent: "center",
  minHeight: "100vh",
  padding: "24px",
};

const FALLBACK_PANEL_STYLE = {
  background: "rgba(255, 255, 255, 0.05)",
  border: "1px solid rgba(255, 255, 255, 0.16)",
  borderRadius: "16px",
  maxWidth: "560px",
  padding: "24px",
  width: "100%",
};

const FALLBACK_BUTTON_STYLE = {
  background: "#f3efe6",
  border: "none",
  borderRadius: "10px",
  color: "#111317",
  cursor: "pointer",
  fontSize: "14px",
  fontWeight: 600,
  marginTop: "8px",
  padding: "10px 16px",
};

export class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
    };
    this.handleReload = this.handleReload.bind(this);
  }

  static getDerivedStateFromError() {
    return {
      hasError: true,
    };
  }

  componentDidCatch(error, errorInfo) {
    logRendererDiagnostic("renderer_root_error_boundary", {
      componentStack: errorInfo?.componentStack ?? "",
      error,
    });
  }

  handleReload() {
    try {
      globalThis.window?.location?.reload();
    } catch {
      // ignore reload errors in test/runtime shims
    }
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <main role="alert" style={FALLBACK_CONTAINER_STYLE}>
        <section style={FALLBACK_PANEL_STYLE}>
          <p style={{ margin: "0 0 8px", opacity: 0.78 }}>Renderer Recovery</p>
          <h1 style={{ fontSize: "24px", margin: "0 0 10px" }}>界面加载失败</h1>
          <p style={{ lineHeight: 1.6, margin: "0 0 12px", opacity: 0.9 }}>
            启动过程中发生异常，已切换到安全兜底页面，避免出现空白界面。
          </p>
          <button onClick={this.handleReload} style={FALLBACK_BUTTON_STYLE} type="button">
            重新加载
          </button>
        </section>
      </main>
    );
  }
}
