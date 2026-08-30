import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import type { ReactNode } from "react";
import { useIsMobile } from "../hooks/useIsMobile";

/**
 * 按断点切换 antd 主题 token：
 * 移动端字号更小、控件更矮、圆角更收敛，统一由 antd 应用，
 * 替代在 index.css 里逐个组件写 !important 的维护方式。
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const isMobile = useIsMobile();

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#1677ff",
          colorInfo: "#1677ff",
          colorBgLayout: "#f5f9ff",
          colorText: "#1d2939",
          fontSize: isMobile ? 13 : 14,
          controlHeight: isMobile ? 30 : 32,
          controlHeightLG: isMobile ? 36 : 40,
          controlHeightSM: isMobile ? 22 : 24,
          borderRadius: isMobile ? 4 : 6,
        },
        components: {
          Layout: {
            headerBg: "#ffffff",
            siderBg: "#ffffff",
            bodyBg: "#f5f9ff",
          },
          Menu: {
            itemColor: "#344054",
            itemSelectedColor: "#1677ff",
            itemSelectedBg: "#e6f4ff",
            itemHoverBg: "#f0f7ff",
          },
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
}
