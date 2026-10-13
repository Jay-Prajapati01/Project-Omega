import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Shell } from "@/components/Shell";
import { ThemeEffect } from "@/components/ThemeEffect";
import { CloudAuthGate } from "@/components/CloudAuthGate";
import { CookieConsent } from "@/components/CookieConsent";
import { metadataBaseForSite } from "@/lib/site-metadata";

export const metadata: Metadata = {
  metadataBase: metadataBaseForSite(),
  title: "MindMesh | Your buddy who remembers everything you save",
  description:
    "Your buddy that remembers everything you save — videos, PDFs, notes, links and more, all in one place you can talk to.",
  robots: { index: false, follow: true },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeEffect />
        <Providers>
          <CloudAuthGate><Shell>{children}</Shell></CloudAuthGate>
          <CookieConsent />
        </Providers>
      </body>
    </html>
  );
}
