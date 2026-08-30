import { useCallback, type RefObject } from "react";

/** 滚动到聊天列表底部 */
export function useAutoScroll(listRef: RefObject<HTMLDivElement | null>) {
  return useCallback(() => {
    setTimeout(() => {
      listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
    }, 50);
  }, [listRef]);
}
