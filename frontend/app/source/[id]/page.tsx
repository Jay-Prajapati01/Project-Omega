"use client";
import { use, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cloudMode } from "@/lib/auth";

export default function SourceFilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [message, setMessage] = useState("Opening your file…");
  const [fileUrl, setFileUrl] = useState("");
  useEffect(() => {
    let active = true;
    let objectUrl = "";
    async function open() {
      try {
        if (cloudMode) {
          const { data } = await api.get(`/sources/${encodeURIComponent(id)}/link`);
          if (active) window.location.replace(data.url);
        } else {
          const { data } = await api.get(`/sources/${encodeURIComponent(id)}/view`, { responseType: "blob" });
          if (active) { objectUrl = URL.createObjectURL(data); setFileUrl(objectUrl); }
        }
      } catch { if (active) setMessage("Unable to open this file. Check your account access and try again."); }
    }
    void open();
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [id]);
  return fileUrl ? <><a className="font-bold underline" href={fileUrl} download>Download file</a><iframe title="Saved file" src={fileUrl} sandbox="" className="mt-4 h-[80vh] w-full rounded-xl border" /></> : <p role="status">{message}</p>;
}
