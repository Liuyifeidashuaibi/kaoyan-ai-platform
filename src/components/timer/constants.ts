/** Pastel palette for subjects and charts */
export const PASTEL_COLORS = [
  "#F9A8D4", // pink
  "#93C5FD", // blue
  "#6EE7B7", // mint
  "#FDE68A", // yellow
  "#C4B5FD", // lavender
  "#FCA5A5", // coral
  "#7DD3FC", // sky
  "#A7F3D0", // green
] as const;

export function assignPastelColor(index: number): string {
  return PASTEL_COLORS[index % PASTEL_COLORS.length];
}
