// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { FloatingRuntimeModal } from "../../src/features/purchase-system/components/floating_runtime_modal.jsx";


function ModalHarness() {
  const [isOpen, setIsOpen] = useState(true);
  const [position, setPosition] = useState({ x: 120, y: 80 });
  const [size, setSize] = useState({ width: 640, height: 360 });

  return (
    <div>
      <button type="button" onClick={() => setIsOpen(false)}>外部关闭</button>
      <button type="button" onClick={() => setIsOpen(true)}>外部打开</button>
      <FloatingRuntimeModal
        isOpen={isOpen}
        position={position}
        size={size}
        title="最近事件"
        onClose={() => setIsOpen(false)}
        onPositionChange={setPosition}
        onSizeChange={setSize}
      >
        <div>modal body</div>
      </FloatingRuntimeModal>
    </div>
  );
}


describe("floating runtime modal", () => {
  it("renders the requested frame position and size", async () => {
    render(
      <FloatingRuntimeModal
        isOpen
        position={{ x: 120, y: 80 }}
        size={{ width: 640, height: 360 }}
        title="最近事件"
        onClose={() => {}}
        onPositionChange={() => {}}
        onSizeChange={() => {}}
      >
        <div>modal body</div>
      </FloatingRuntimeModal>,
    );

    const dialog = await screen.findByRole("dialog", { name: "最近事件" });
    expect(dialog).toHaveStyle({
      left: "120px",
      top: "80px",
      width: "640px",
      height: "360px",
    });
  });

  it("reports the next position when dragging the title bar", async () => {
    const handlePositionChange = vi.fn();

    render(
      <FloatingRuntimeModal
        isOpen
        position={{ x: 120, y: 80 }}
        size={{ width: 640, height: 360 }}
        title="最近事件"
        onClose={() => {}}
        onPositionChange={handlePositionChange}
        onSizeChange={() => {}}
      >
        <div>modal body</div>
      </FloatingRuntimeModal>,
    );

    const dragHandle = await screen.findByTestId("floating-runtime-modal-drag");
    fireEvent.mouseDown(dragHandle, { clientX: 140, clientY: 100 });
    fireEvent.mouseMove(window, { clientX: 200, clientY: 145 });
    fireEvent.mouseUp(window);

    expect(handlePositionChange).toHaveBeenCalledWith({ x: 180, y: 125 });
  });

  it("reports the next size when dragging the resize handle", async () => {
    const handleSizeChange = vi.fn();

    render(
      <FloatingRuntimeModal
        isOpen
        position={{ x: 120, y: 80 }}
        size={{ width: 640, height: 360 }}
        title="最近事件"
        onClose={() => {}}
        onPositionChange={() => {}}
        onSizeChange={handleSizeChange}
      >
        <div>modal body</div>
      </FloatingRuntimeModal>,
    );

    const resizeHandle = await screen.findByTestId("floating-runtime-modal-resize");
    fireEvent.mouseDown(resizeHandle, { clientX: 760, clientY: 440 });
    fireEvent.mouseMove(window, { clientX: 820, clientY: 500 });
    fireEvent.mouseUp(window);

    expect(handleSizeChange).toHaveBeenCalledWith({ width: 700, height: 420 });
  });

  it("keeps the latest frame when the parent closes and reopens the modal", async () => {
    render(<ModalHarness />);

    const dragHandle = await screen.findByTestId("floating-runtime-modal-drag");
    fireEvent.mouseDown(dragHandle, { clientX: 140, clientY: 100 });
    fireEvent.mouseMove(window, { clientX: 200, clientY: 145 });
    fireEvent.mouseUp(window);

    const resizeHandle = await screen.findByTestId("floating-runtime-modal-resize");
    fireEvent.mouseDown(resizeHandle, { clientX: 760, clientY: 440 });
    fireEvent.mouseMove(window, { clientX: 820, clientY: 500 });
    fireEvent.mouseUp(window);

    fireEvent.click(screen.getByRole("button", { name: "外部关闭" }));
    expect(screen.queryByRole("dialog", { name: "最近事件" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "外部打开" }));
    const dialog = await screen.findByRole("dialog", { name: "最近事件" });
    expect(dialog).toHaveStyle({
      left: "180px",
      top: "125px",
      width: "700px",
      height: "420px",
    });
  });
});
