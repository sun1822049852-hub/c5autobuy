import { useState } from "react";


export function useFloatingRuntimeModalState({
  initialOpen = false,
  initialPosition,
  initialSize,
} = {}) {
  const [isOpen, setIsOpen] = useState(Boolean(initialOpen));
  const [position, setPosition] = useState(initialPosition || { x: 120, y: 80 });
  const [size, setSize] = useState(initialSize || { width: 640, height: 360 });

  return {
    isOpen,
    onClose: () => {
      setIsOpen(false);
    },
    onOpen: () => {
      setIsOpen(true);
    },
    onPositionChange: (nextPosition) => {
      setPosition((current) => ({
        ...current,
        ...nextPosition,
      }));
    },
    onSizeChange: (nextSize) => {
      setSize((current) => ({
        ...current,
        ...nextSize,
      }));
    },
    position,
    size,
  };
}
