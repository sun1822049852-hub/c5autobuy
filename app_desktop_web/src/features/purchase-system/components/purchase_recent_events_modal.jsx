import { FloatingRuntimeModal } from "./floating_runtime_modal.jsx";
import { PurchaseRecentEvents } from "./purchase_recent_events.jsx";


export function PurchaseRecentEventsModal({
  events,
  isOpen,
  onClose,
  onPositionChange,
  onSizeChange,
  position,
  size,
}) {
  return (
    <FloatingRuntimeModal
      isOpen={isOpen}
      onClose={onClose}
      onPositionChange={onPositionChange}
      onSizeChange={onSizeChange}
      position={position}
      size={size}
      title="最近事件"
    >
      <PurchaseRecentEvents events={events} />
    </FloatingRuntimeModal>
  );
}
