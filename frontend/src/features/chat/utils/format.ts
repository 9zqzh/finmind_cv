/** 距离展示：不足 1 公里用米 */
export function formatDistance(distance: number | null | undefined) {
  if (!distance) return null;
  return distance >= 1000
    ? `${(distance / 1000).toFixed(1)} 公里`
    : `${Math.round(distance)} 米`;
}
