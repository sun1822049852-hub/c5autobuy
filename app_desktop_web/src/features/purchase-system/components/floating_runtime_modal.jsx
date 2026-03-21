import { useEffect, useRef } from "react";


export function FloatingRuntimeModal({
  children,
  isOpen,
  onClose,
  onPositionChange,
  onSizeChange,
  position,
  size,
  title,
}) {
  const dragStateRef = useRef(null);

  useEffect(() => {
    if (!isOpen) {
      dragStateRef.current = null;
      return undefined;
    }

    function handleMouseMove(event) {
      const dragState = dragStateRef.current;
      if (!dragState) {
        return;
      }

      const deltaX = event.clientX - dragState.startX;
      const deltaY = event.clientY - dragState.startY;

      if (dragState.mode === "move") {
        onPositionChange?.({
          x: dragState.baseX + deltaX,
          y: dragState.baseY + deltaY,
        });
        return;
      }

      onSizeChange?.({
        width: dragState.baseWidth + deltaX,
        height: dragState.baseHeight + deltaY,
      });
    }

    function handleMouseUp() {
      dragStateRef.current = null;
    }

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isOpen, onPositionChange, onSizeChange]);

  if (!isOpen) {
    return null;
  }

  const left = Number(position?.x ?? 120);
  const top = Number(position?.y ?? 80);
  const width = Number(size?.width ?? 640);
  const height = Number(size?.height ?? 360);

  return (
    <div className="surface-backdrop">
      <section
        aria-label={title}
        aria-modal="true"
        className="dialog-surface"
        role="dialog"
        style={{
          height: `${height}px`,
          left: `${left}px`,
          position: "fixed",
          top: `${top}px`,
          width: `${width}px`,
        }}
      >
        <div
          className="surface-header"
          data-testid="floating-runtime-modal-drag"
          onMouseDown={(event) => {
            dragStateRef.current = {
              baseX: left,
              baseY: top,
              mode: "move",
              startX: event.clientX,
              startY: event.clientY,
            };
          }}
        >
          <h2 className="surface-title">{title}</h2>
          <button className="ghost-button" type="button" onClick={() => onClose?.()}>
            关闭
          </button>
        </div>

        <div className="drawer-stack">
          {children}
        </div>

        <div
          aria-hidden="true"
          data-testid="floating-runtime-modal-resize"
          style={{
            bottom: "12px",
            cursor: "nwse-resize",
            height: "16px",
            position: "absolute",
            right: "12px",
            width: "16px",
          }}
          onMouseDown={(event) => {
            dragStateRef.current = {
              baseHeight: height,
              baseWidth: width,
              mode: "resize",
              startX: event.clientX,
              startY: event.clientY,
            };
          }}
        />
      </section>
    </div>
  );
}
