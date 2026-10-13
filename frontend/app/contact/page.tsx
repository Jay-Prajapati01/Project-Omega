import type { Metadata } from "next";
import { ContactPage } from "@/components/landing/ContactPage";

const TITLE = "Contact MindMesh | Talk to the team";
const DESC =
  "Questions, partnerships or account support? Send the MindMesh team a message and we'll get back to you.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESC,
  robots: { index: true, follow: true },
  openGraph: {
    title: TITLE,
    description: DESC,
    type: "website",
    images: [{ url: "/share-card.png", width: 1200, height: 630, alt: "Contact the MindMesh team" }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESC,
    images: ["/share-card.png"],
  },
};

export default function Contact() {
  return <ContactPage />;
}
