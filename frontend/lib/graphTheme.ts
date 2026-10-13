export interface GraphTheme {
  canvas: string;
  background: string;
  grid: string;
  controlBackground: string;
  controlForeground: string;
  minimapBackground: string;
  minimapMask: string;
  nodeText: string;
  nodeBackground: string;
  nodeBorder: string;
  edge: string;
  edgeLabel: string;
  edgeLabelBackground: string;
  panelBackground: string;
  panelBorder: string;
}

export function getGraphTheme(resolvedTheme: "dark" | "light" | string): GraphTheme {
  const isDark = resolvedTheme !== "light";

  if (isDark) {
    return {
      canvas: "#1E150E",
      background: "#1E150E",
      grid: "#3A2C1E",
      controlBackground: "#241A12",
      controlForeground: "#F5EEDD",
      minimapBackground: "#241A12",
      minimapMask: "rgba(30, 21, 14, 0.75)",
      nodeText: "#F5EEDD",
      nodeBackground: "#241A12",
      nodeBorder: "#F5EEDD",
      edge: "rgba(245, 238, 221, 0.30)",
      edgeLabel: "#BCA88F",
      edgeLabelBackground: "#241A12",
      panelBackground: "#241A12",
      panelBorder: "#F5EEDD",
    };
  }

  return {
    canvas: "#FFF6E9",
    background: "#FFF6E9",
    grid: "#EFE3CF",
    controlBackground: "#FFFFFF",
    controlForeground: "#1A120B",
    minimapBackground: "#FFFFFF",
    minimapMask: "rgba(255, 246, 233, 0.75)",
    nodeText: "#1A120B",
    nodeBackground: "#FFFFFF",
    nodeBorder: "#1A120B",
    edge: "rgba(26, 18, 11, 0.30)",
    edgeLabel: "#6B5B4D",
    edgeLabelBackground: "#F5EBDD",
    panelBackground: "#FFFFFF",
    panelBorder: "#1A120B",
  };
}
