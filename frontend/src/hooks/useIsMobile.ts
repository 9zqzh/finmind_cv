import { useSyncExternalStore } from "react";

const DEFAULT_BREAKPOINT = 767;

function buildQuery(breakpoint: number) {
  return `(max-width: ${breakpoint}px)`;
}

function subscribe(callback: () => void, query: string) {
  const mql = window.matchMedia(query);
  mql.addEventListener("change", callback);
  return () => mql.removeEventListener("change", callback);
}

/**
 * 响应式断点判断：不依赖 antd 的 Grid.useBreakpoint，可在任意组件/逻辑中使用。
 * @param breakpoint 判定为移动端的最大宽度（px），默认 767
 */
export function useIsMobile(breakpoint: number = DEFAULT_BREAKPOINT) {
  const query = buildQuery(breakpoint);
  return useSyncExternalStore(
    (callback) => subscribe(callback, query),
    () => window.matchMedia(query).matches,
  );
}
