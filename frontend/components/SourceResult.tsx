import { Badge, Card } from "@/components/ui";
import { SourceItem } from "@/lib/api";

export function SourceResult({ item }: { item: SourceItem }) {
  return (
    <Card className="mt-6">
      <h2 className="text-lg font-semibold text-foreground">{item.title || item.source_id}</h2>
      <p className="mb-3 text-sm text-foreground-3">
        {item.channel ? `${item.channel} · ` : ""}
        {item.chunks_indexed} chunks indexed
      </p>
      {item.summary && (
        <p className="mb-4 text-sm leading-relaxed text-foreground-2">
          {item.summary}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        {item.key_topics.map((t) => (
          <Badge key={t}>{t}</Badge>
        ))}
      </div>
    </Card>
  );
}
