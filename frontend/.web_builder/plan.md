# 学院教学小助手 — 移动端适配计划

> 使用 web-builder 计划驱动工作流，对现有 React + Vite + Ant Design 项目进行移动端（响应式）适配改造。

## 背景

项目为前后端分离的学院教学小助手，前端位于 `front_end/web`，技术栈 React 18 + Vite + Ant Design 5 + TypeScript。

## 现状盘点

### 已具备的移动端基础 ✅
- `AppLayout.tsx`：已用 `Grid.useBreakpoint()` 判断 `isMobile`，移动端侧边栏转 Drawer 抽屉 + 汉堡菜单
- `index.css`：全局 `overflow-x: hidden`
- `SchedulePage`：课表网格已有 `.schedule-grid-scroll` 横向滚动
- `CompetitionPage`：竞赛卡片用 `Col xs={24}` 栅格，移动端单列

### 已确认的项目自带移动端适配 ✅（深入核查后）

项目已有完善响应式基础，多数页面已适配：

| 页面 | 移动端处理 |
|------|-----------|
| 课表 | `schedule-mobile-list` 卡片视图 |
| 成绩 | `mobile-card-list` 卡片视图 |
| 培养方案 | `mobile-card-list` 卡片视图 |
| 教室课表 | `mobile-card-list` + 表格横向滚动 |
| 登录页 | 卡片 `min(400px, calc(100vw-32px))` |
| AI对话 | 输入框/消息/思考气泡全适配 |
| 竞赛弹窗 | `width={isMobile ? calc(100vw-32px) : 700}` |
| 全局 | `app-content` padding、44px 触控 |

**下一步**：启动项目，用浏览器在移动端视口实测，找出真正遗漏项。

## 适配策略

统一遵循 Ant Design 响应式 + 自定义媒体查询：
- 断点：`<576` 手机 / `576-768` 平板 / `>768` 桌面（对齐 antd md 断点）
- Table：移动端开启横向滚动（`scroll={{ x: ... }}`）或卡片化
- 固定宽度容器（登录卡片、Modal）：改为 `max-width: 100%` + `width: 100%`
- 布局间距：移动端 Content padding 由 24 缩至 12-16
- 触控：点击区域 ≥44px

## 改造清单

- [ ] P0-1 全局布局：Content padding 响应式、头部标题字号缩放
- [ ] P0-2 登录页：卡片宽度响应式，窄屏占满并留边距
- [ ] P0-3 AI对话：消息容器、输入框、思考气泡移动端适配；工具结果 Table 横向滚动
- [ ] P0-4 成绩页：Table 横向滚动或卡片化
- [ ] P0-5 培养方案：Table 横向滚动
- [ ] P1-1 教室课表：Table 横向滚动 + Select 布局堆叠
- [ ] P1-2 学院资讯：图片宽度响应式 + List 布局
- [ ] P1-3 竞赛页：Modal 宽度响应式
- [ ] P1-4 知识库：布局确认与适配
- [ ] P2 验证：TypeScript 编译 + 多断点浏览器检查（无横向滚动、点击区≥44px）

## 技术方案

- 全局：使用 antd `Grid.useBreakpoint()` 或 CSS 媒体查询
- Table 移动端：`scroll={{ x: 800 }}` 保证横向滚动不破坏布局
- 响应式宽度：`width: "100%", maxWidth: 400` 替代固定 `width: 400`
- Modal：`width="90%"` + `maxWidth: 700`
- Content padding：内联样式改为响应式（用 breakpoint 判断）

## 验证标准

- [ ] 手机（375px）、平板（768px）、桌面（1440px）三档正常
- [ ] 手机端无横向滚动条
- [ ] 点击区域 ≥44px
- [ ] TypeScript 编译通过，浏览器无控制台报错

## 进度

- [x] Phase 0 需求与现状盘点
- [ ] Phase 1 逐页适配改造
- [ ] Phase 2 验证与收尾
