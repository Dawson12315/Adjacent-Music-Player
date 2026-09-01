import { useEffect } from "react";

/**
 * Closes a transient surface on an outside click or Escape.
 *
 * The old menus had four layers of stopPropagation defending against a document listener
 * that was never written — there was no addEventListener anywhere in the app — so they
 * could only be dismissed by re-clicking the trigger or picking an item.
 *
 * Pointerdown rather than click, so the menu closes on press rather than release.
 */
export function useDismissable(isOpen, onDismiss) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    function handlePointerDown(event) {
      // Anything inside a menu, or the trigger that owns one, handles its own clicks.
      if (event.target.closest?.("[data-dismissable-root]")) {
        return;
      }

      onDismiss();
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        onDismiss();
      }
    }

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onDismiss]);
}
