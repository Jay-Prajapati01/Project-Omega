import Link from "next/link";
import { Button } from "@/components/ui";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Page not found | MindMesh",
  description: "This MindMesh page could not be found.",
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <h2 className="mb-2 text-4xl font-bold text-brand">404</h2>
      <p className="mb-6 text-sm text-gray-400">This page does not exist.</p>
      <Link href="/">
        <Button>Back to dashboard</Button>
      </Link>
    </div>
  );
}
