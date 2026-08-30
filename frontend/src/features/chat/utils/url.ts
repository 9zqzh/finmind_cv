/** 生成高德 URI 导航链接（步行） */
export function amapNavigationUrl(location: string, name?: string) {
  const [lng, lat] = String(location ?? "").split(",");
  if (!lng || !lat) return null;
  const label = name ? `,${encodeURIComponent(name)}` : "";
  return `https://uri.amap.com/navigation?to=${lng},${lat}${label}&mode=walk&coordinate=gaode`;
}

/** 只允许打开后端登记的高德 HTTPS URI，拒绝模型文本或异常载荷注入链接。 */
export function trustedAmapUrl(value: string | null | undefined) {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === "uri.amap.com" ? url.href : null;
  } catch {
    return null;
  }
}

export function trustedImageUrl(value: unknown) {
  if (typeof value !== "string" || !value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}
