export interface ChartTheme {
  background: string;
  text: string;
  mutedText: string;
  grid: string;
  tooltipBackground: string;
  tooltipBorder: string;
  tooltipText: string;
  brand: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
}

export function getChartTheme(resolvedTheme: "dark" | "light" | string): ChartTheme {
  const isDark = resolvedTheme !== "light";

  if (isDark) {
    return {
      background: "#241A12",
      text: "#F5EEDD",
      mutedText: "#BCA88F",
      grid: "rgba(245, 238, 221, 0.12)",
      tooltipBackground: "#241A12",
      tooltipBorder: "#F5EEDD",
      tooltipText: "#F5EEDD",
      brand: "#FF6B00",
      success: "#FF6B00",
      warning: "#E8930C",
      danger: "#C62828",
      info: "#BCA88F",
    };
  }

  return {
    background: "#FFFFFF",
    text: "#1A120B",
    mutedText: "#6B5B4D",
    grid: "rgba(26, 18, 11, 0.10)",
    tooltipBackground: "#FFFFFF",
    tooltipBorder: "#1A120B",
    tooltipText: "#1A120B",
    brand: "#FF5C00",
    success: "#168A4A",
    warning: "#B96A00",
    danger: "#C62828",
    info: "#6B5B4D",
  };
}
