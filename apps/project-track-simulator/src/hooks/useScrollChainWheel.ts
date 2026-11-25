import { useEffect, type RefObject } from "react";

/** Lets vertical wheel events bubble to an ancestor scroll area when this node only scrolls horizontally. */
export function useScrollChainWheel(ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    const onWheel = (e: WheelEvent) => {
      const absY = Math.abs(e.deltaY);
      const absX = Math.abs(e.deltaX);
      const mostlyVertical = absY >= absX;

      if (mostlyVertical) {
        const canScrollY = node.scrollHeight > node.clientHeight + 1;
        if (!canScrollY) {
          let parent: HTMLElement | null = node.parentElement;
          while (parent) {
            const { overflowY } = getComputedStyle(parent);
            const scrollable =
              (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") &&
              parent.scrollHeight > parent.clientHeight + 1;
            if (scrollable) {
              parent.scrollTop += e.deltaY;
              e.preventDefault();
              return;
            }
            if (parent.classList.contains("rv-scroll")) {
              parent.scrollTop += e.deltaY;
              e.preventDefault();
              return;
            }
            parent = parent.parentElement;
          }
          const root = document.scrollingElement;
          if (root && root.scrollHeight > root.clientHeight + 1) {
            root.scrollTop += e.deltaY;
            e.preventDefault();
          }
        }
      }

      if (absX > 0 || e.shiftKey) {
        const delta = e.shiftKey && absY > absX ? e.deltaY : e.deltaX || e.deltaY;
        const maxLeft = node.scrollWidth - node.clientWidth;
        if (maxLeft > 1) {
          const next = Math.min(maxLeft, Math.max(0, node.scrollLeft + delta));
          if (next !== node.scrollLeft) {
            node.scrollLeft = next;
            e.preventDefault();
          }
        }
      }
    };

    node.addEventListener("wheel", onWheel, { passive: false });
    return () => node.removeEventListener("wheel", onWheel);
  }, [ref]);
}