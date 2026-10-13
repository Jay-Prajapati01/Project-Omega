"use client";

import { useEffect } from "react";
import { trackEvent } from "@/lib/analytics";

export function ContactConversion() {
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("source") === "contact") {
      void trackEvent("generate_lead", { form_name: "contact" });
    }
  }, []);
  return null;
}
