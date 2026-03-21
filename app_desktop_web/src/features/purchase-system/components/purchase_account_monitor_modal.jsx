import { FloatingRuntimeModal } from "./floating_runtime_modal.jsx";
import { PurchaseAccountTable } from "./purchase_account_table.jsx";


export function PurchaseAccountMonitorModal({
  isOpen,
  onClose,
  onPositionChange,
  onSizeChange,
  position,
  rows,
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
      title="查看账号详情"
    >
      <PurchaseAccountTable rows={rows} />
    </FloatingRuntimeModal>
  );
}
