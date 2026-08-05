import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: "#1677ff",
          colorInfo: "#1677ff",
          colorBgLayout: "#f5f9ff",
          colorText: "#1d2939",
          borderRadius: 6,
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
      <App />
    </ConfigProvider>
  </StrictMode>,
);
