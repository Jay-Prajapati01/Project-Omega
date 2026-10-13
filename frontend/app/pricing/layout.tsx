import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "MindMesh",
  description: "MindMesh plans are not publicly listed yet.",
  robots: { index: false, follow: false },
  openGraph: { title: "MindMesh", description: "MindMesh plans are not publicly listed yet." },
  twitter: { card: "summary", title: "MindMesh", description: "MindMesh plans are not publicly listed yet." },
};

export default function PricingLayout({ children }: { children: React.ReactNode }) { return children; }
