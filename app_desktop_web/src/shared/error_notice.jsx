import { FeedbackDialog } from "./feedback_dialog.jsx";


export function ErrorNotice({ details = [], message, onClose, title = "操作提示" }) {
  void details;

  return (
    <FeedbackDialog
      actionLabel="知道了"
      isOpen={Boolean(message)}
      message={message}
      onClose={onClose}
      title={title}
    />
  );
}
