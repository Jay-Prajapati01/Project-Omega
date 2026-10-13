"use client";

import Image from "next/image";
import Link from "next/link";
import { memo, useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlowProvider,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
  useReactFlow,
} from "reactflow";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle, ArrowUpRight, Brain, CircleHelp, ExternalLink, FileText,
  Image as ImageIcon, Instagram, Network, Play, RefreshCw, Search, Youtube,
} from "lucide-react";
import { getGraph, listSources, rebuildGraph, type GraphEdge, type GraphNode, type SourceItem } from "@/lib/api";
import { cloudMode } from "@/lib/auth";
import { cleanLabel, SOURCE_LABELS } from "@/components/graph/graphModel";

type GraphData = { nodes: GraphNode[]; edges: GraphEdge[] };
type OrbitalNodeData = {
  id: string;
  label: string;
  kind: "brand" | "concept" | "source" | "cluster";
  color?: string;
  count?: number;
  source?: SourceItem;
  active?: boolean;
  clusterId?: string;
  width?: number;
  height?: number;
};

const FEATURE_CLUSTERS = [
  { id: "youtube", label: "YouTube", color: "#E62117", tint: "rgba(230,33,23,.075)", sourceType: "youtube" },
  { id: "instagram", label: "Instagram", color: "#C13584", tint: "rgba(193,53,132,.075)", sourceType: "instagram" },
] as const;
type FeatureCluster = (typeof FEATURE_CLUSTERS)[number];
function clusterForType(sourceType?: string): FeatureCluster | undefined {
  return FEATURE_CLUSTERS.find((cluster) => cluster.sourceType === sourceType);
}
const SIDES = [
  { id: "top", position: Position.Top, opposite: "bottom" },
  { id: "right", position: Position.Right, opposite: "left" },
  { id: "bottom", position: Position.Bottom, opposite: "top" },
  { id: "left", position: Position.Left, opposite: "right" },
] as const;
function sideForAngle(angle: number) {
  const x = Math.cos(angle), y = Math.sin(angle);
  return Math.abs(x) >= Math.abs(y) ? (x >= 0 ? "right" : "left") : (y >= 0 ? "bottom" : "top");
}

function SourceFallback({ type }: { type: string }) {
  const Icon = type === "youtube" ? Youtube : type === "instagram" ? Instagram : type === "pdf" || type === "document" ? FileText : type === "audio" ? Play : type === "web" ? ImageIcon : CircleHelp;
  const label = SOURCE_LABELS[type] ?? "Saved source";
  return (
    <div className={`source-fallback source-fallback-${type}`} aria-label={`${label} thumbnail placeholder`}>
      <span className="source-fallback-mark"><Icon size={25} strokeWidth={2.4} /></span>
      <span className="source-fallback-label">{label}</span>
      <span className="source-fallback-wordmark">MINDMESH</span>
    </div>
  );
}

function originalSourceUrl(source?: SourceItem) {
  if (!source) return undefined;
  if (source.url) return source.url;
  if (source.source_type === "youtube") return `https://www.youtube.com/watch?v=${encodeURIComponent(source.source_id)}`;
  if (source.source_type === "instagram") return `https://www.instagram.com/reel/${encodeURIComponent(source.source_id)}/`;
  return undefined;
}

function BrandNode() {
  return (
    <div className="orbital-brand-node" aria-label="MindMesh knowledge hub">
      {SIDES.map((side) => <Handle key={side.id} id={side.id} type="source" position={side.position} className="!opacity-0" />)}
      <div className="orbital-brand-mark"><Image src="/logo.png" alt="MindMesh logo" fill sizes="84px" priority /></div>
      <strong>MindMesh</strong>
      <span>Your knowledge</span>
      {SIDES.map((side) => <Handle key={`target-${side.id}`} id={`target-${side.id}`} type="target" position={side.position} className="!opacity-0" />)}
    </div>
  );
}

function ClusterBackdrop({ data }: NodeProps<OrbitalNodeData>) {
  const cluster = FEATURE_CLUSTERS.find((item) => item.id === data.clusterId) ?? FEATURE_CLUSTERS[0];
  return <div className="feature-cluster-backdrop" style={{ width: data.width, height: data.height, "--cluster-color": cluster.color, "--cluster-tint": cluster.tint } as React.CSSProperties}><span className="feature-cluster-dot" />{cluster.label}<small>{data.count ?? 0} items</small></div>;
}

function ConceptCard({ data, selected }: NodeProps<OrbitalNodeData>) {
  return (
    <button className={`orbital-concept-node${selected || data.active ? " is-active" : ""}`} style={{ "--node-accent": data.color ?? "#ff5c00" } as React.CSSProperties} title={`${data.label} · ${data.count ?? 0} ${data.count === 1 ? "mention" : "mentions"}`}>
      {SIDES.map((side) => <Handle key={`target-${side.id}`} id={`target-${side.id}`} type="target" position={side.position} className="!opacity-0" />)}
      <span className="orbital-concept-icon"><Brain size={17} /></span>
      <span className="orbital-concept-copy"><strong>{data.label}</strong><small>{data.count ?? 0} {data.count === 1 ? "mention" : "mentions"}</small></span>
      {SIDES.map((side) => <Handle key={`source-${side.id}`} id={`source-${side.id}`} type="source" position={side.position} className="!opacity-0" />)}
    </button>
  );
}
const MemoConceptCard = memo(ConceptCard);

function SourceCard({ data, selected }: NodeProps<OrbitalNodeData>) {
  const source = data.source;
  const type = source?.source_type ?? "web";
  const href = originalSourceUrl(source);
  return (
    <div className={`orbital-source-node${selected ? " is-active" : ""}`} style={{ "--node-accent": data.color ?? "#ff5c00" } as React.CSSProperties} title={source?.title || "Saved source"}>
      {SIDES.map((side) => <Handle key={`target-${side.id}`} id={`target-${side.id}`} type="target" position={side.position} className="!opacity-0" />)}
      <a className="orbital-source-image" href={href} target={href ? "_blank" : undefined} rel={href ? "noopener noreferrer" : undefined} aria-label={`Open original ${SOURCE_LABELS[type] ?? type} content`} onClick={(event) => { if (!href) event.preventDefault(); event.stopPropagation(); }}>
        {source?.thumbnail ? <img src={source.thumbnail} alt={source.title ? `Thumbnail for ${source.title}` : "Saved source thumbnail"} loading="lazy" onError={(event) => { event.currentTarget.style.display = "none"; event.currentTarget.parentElement?.classList.add("thumbnail-failed"); }} /> : null}
        {!source?.thumbnail && <SourceFallback type={type} />}
        {source?.thumbnail && <span className="thumbnail-fallback"><SourceFallback type={type} /></span>}
        <span className="orbital-source-badge">{type === "youtube" ? <Youtube size={12} /> : type === "instagram" ? <Instagram size={12} /> : <FileText size={12} />}{SOURCE_LABELS[type] ?? type}</span>
        {href && <span className="source-open-hint"><ExternalLink size={12} /> Open original</span>}
      </a>
      <span className="orbital-source-title">{source?.title || source?.file_name || "Untitled saved source"}</span>
      <span className="orbital-source-meta">{source?.channel || source?.created_at?.slice(0, 10) || "Saved source"}</span>
      {SIDES.map((side) => <Handle key={`source-${side.id}`} id={`source-${side.id}`} type="source" position={side.position} className="!opacity-0" />)}
    </div>
  );
}
const MemoSourceCard = memo(SourceCard);

const nodeTypes = { brand: BrandNode, cluster: ClusterBackdrop, concept: MemoConceptCard, source: MemoSourceCard };
const MAX_CONCEPTS = 24;
const MAX_SOURCES = 24;
const HUB_X = 768;
const HUB_Y = 500;
const HUB_CENTER_X = HUB_X + 87;
const HUB_CENTER_Y = HUB_Y + 87;

type PositionOverrides = Record<string, { x: number; y: number }>;
type ConceptPlacement = { concept: GraphNode; clusterId: string; nodeId: string };
function buildOrbitalGraph(graph: GraphData, sources: SourceItem[], filter: string, query: string, selectedId: string | null, overrides: PositionOverrides) {
  const supportedSourceIds = new Set(sources.filter((source) => FEATURE_CLUSTERS.some((cluster) => cluster.sourceType === source.source_type)).map((source) => source.source_id));
  const eligibleSources = sources.filter((source) => supportedSourceIds.has(source.source_id) && (filter === "all" || source.source_type === filter));
  const eligibleSourceIds = new Set(eligibleSources.map((source) => source.source_id));
  const sourceTypeById = new Map(eligibleSources.map((source) => [source.source_id, source.source_type]));
  const edges = graph.edges.filter((edge) => eligibleSourceIds.has(edge.source_id) && sourceTypeById.get(edge.source_id) === edge.source_type && FEATURE_CLUSTERS.some((cluster) => cluster.sourceType === edge.source_type));
  const conceptById = new Map<string, GraphNode>(graph.nodes.map((node) => [node.id, node] as const));
  const q = query.trim().toLocaleLowerCase();
  const matchingConceptIds = new Set(graph.nodes.filter((node) => !q || cleanLabel(node.label).toLocaleLowerCase().includes(q)).map((node) => node.id));
  const matchingSources = eligibleSources.filter((source) => q && `${source.title ?? ""} ${source.summary ?? ""} ${source.channel ?? ""}`.toLocaleLowerCase().includes(q));
  const directSourceIds = new Set(matchingSources.map((source) => source.source_id));
  const candidateConceptIds = q && matchingConceptIds.size === 0
    ? new Set(edges.filter((edge) => directSourceIds.has(edge.source_id)).flatMap((edge) => [edge.source, edge.target]))
    : matchingConceptIds;
  const candidateEdges = edges.filter((edge) => candidateConceptIds.has(edge.source) || candidateConceptIds.has(edge.target));
  const relatedSourceIds = new Set(candidateEdges.map((edge) => edge.source_id));
  const visibleSources = (q
    ? eligibleSources.filter((source) => relatedSourceIds.has(source.source_id) || directSourceIds.has(source.source_id))
    : eligibleSources
  ).slice(0, MAX_SOURCES);
  const visibleSourceIds = new Set(visibleSources.map((source) => source.source_id));
  const visibleEdges = edges.filter((edge) => visibleSourceIds.has(edge.source_id));

  const memberships = new Map<string, Map<string, GraphNode>>(FEATURE_CLUSTERS.map((cluster) => [cluster.id, new Map<string, GraphNode>()] as const));
  const degree = new Map<string, number>();
  for (const edge of visibleEdges) {
    const cluster = clusterForType(edge.source_type);
    if (!cluster) continue;
    for (const id of [edge.source, edge.target]) {
      const concept = conceptById.get(id);
      if (!concept || !candidateConceptIds.has(id)) continue;
      memberships.get(cluster.id)!.set(id, concept);
      degree.set(id, (degree.get(id) ?? 0) + 1);
    }
  }
  const conceptPlacements: ConceptPlacement[] = [];
  for (const cluster of FEATURE_CLUSTERS) {
    for (const concept of memberships.get(cluster.id)!.values()) {
      conceptPlacements.push({ concept, clusterId: cluster.id, nodeId: `concept:${cluster.id}:${encodeURIComponent(concept.id)}` });
    }
  }
  const concepts = [...new Map<string, GraphNode>(conceptPlacements.map((placement) => [placement.concept.id, placement.concept] as const)).values()]
    .sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) || b.count - a.count || a.label.localeCompare(b.label))
    .slice(0, MAX_CONCEPTS);
  const conceptLimitIds = new Set(concepts.map((concept) => concept.id));
  const visiblePlacements = conceptPlacements.filter((placement) => conceptLimitIds.has(placement.concept.id));
  const placementByKey = new Map<string, ConceptPlacement>(visiblePlacements.map((placement) => [`${placement.clusterId}:${placement.concept.id}`, placement] as const));

  const clusterConcepts = new Map<string, GraphNode[]>(FEATURE_CLUSTERS.map((cluster) => [cluster.id, []]));
  const clusterSources = new Map<string, SourceItem[]>(FEATURE_CLUSTERS.map((cluster) => [cluster.id, []]));
  for (const placement of visiblePlacements) clusterConcepts.get(placement.clusterId)!.push(placement.concept);
  for (const source of visibleSources) {
    const cluster = clusterForType(source.source_type);
    if (cluster) clusterSources.get(cluster.id)!.push(source);
  }

  const center = { x: HUB_CENTER_X, y: HUB_CENTER_Y };
  const clusterLayouts = FEATURE_CLUSTERS.map((cluster) => {
    const itemCount = (clusterConcepts.get(cluster.id)?.length ?? 0) + (clusterSources.get(cluster.id)?.length ?? 0);
    const columns = itemCount > 12 ? 4 : itemCount > 6 ? 3 : 2;
    const rows = Math.ceil(itemCount / columns);
    return { cluster, itemCount, columns, rows, width: columns * 240 + 48, height: Math.max(260, rows * 165 + 100) };
  }).filter((layout) => layout.itemCount > 0);
  const maxWidth = Math.max(0, ...clusterLayouts.map((layout) => layout.width));
  const hasBothClusters = clusterLayouts.length === 2;
  const placements = new Map<string, { x: number; y: number }>();
  clusterLayouts.forEach((layout, index) => {
    const { cluster, width, height } = layout;
    const x = hasBothClusters
      ? center.x + (index === 0 ? -1 : 1) * (maxWidth / 2 + 125) - width / 2
      : center.x - width / 2;
    const y = hasBothClusters ? center.y - height / 2 : center.y + 150;
    placements.set(cluster.id, { x, y });
  });

  const nodes: Node<OrbitalNodeData>[] = clusterLayouts.map(({ cluster, itemCount, width, height }) => {
    const position = placements.get(cluster.id)!;
    return {
      id: `cluster:${cluster.id}`, type: "cluster", position,
      style: { width, height, zIndex: -2 },
      data: { id: cluster.id, label: cluster.label, kind: "cluster", clusterId: cluster.id, width, height, count: itemCount },
      draggable: false, selectable: false, connectable: false, zIndex: -2,
    };
  });
  nodes.push({ id: "mindmesh-hub", type: "brand", position: overrides["mindmesh-hub"] ?? { x: HUB_X, y: HUB_Y }, data: { id: "mindmesh-hub", label: "MindMesh", kind: "brand" }, draggable: true, selectable: false, zIndex: 2 });

  for (const layout of clusterLayouts) {
    const { cluster, columns } = layout;
    const position = placements.get(cluster.id)!;
    const items: Array<{ id: string; concept?: GraphNode; source?: SourceItem }> = [
      ...visiblePlacements.filter((placement) => placement.clusterId === cluster.id).map((placement) => ({ id: placement.nodeId, concept: placement.concept })),
      ...(clusterSources.get(cluster.id) ?? []).map((source) => ({ id: `source:${source.source_id}`, source })),
    ];
    items.forEach((item, index) => {
      const col = index % columns;
      const row = Math.floor(index / columns);
      const x = position.x + 24 + col * 240;
      const y = position.y + 62 + row * 165;
      if (item.concept) {
        const placement = placementByKey.get(`${cluster.id}:${item.concept.id}`)!;
        nodes.push({
          id: placement.nodeId, type: "concept", position: overrides[placement.nodeId] ?? { x, y },
          data: { id: item.concept.id, label: cleanLabel(item.concept.label), kind: "concept", count: item.concept.count, color: cluster.color, clusterId: cluster.id, active: selectedId === item.concept.id },
          draggable: true,
        });
      } else if (item.source) {
        nodes.push({
          id: item.id, type: "source", position: overrides[item.id] ?? { x, y },
          data: { id: item.source.source_id, label: item.source.title || "Saved source", kind: "source", source: item.source, clusterId: cluster.id, color: cluster.color },
          draggable: true,
        });
      }
    });
  }

  const finalConceptIds = new Set(visiblePlacements.map((placement) => placement.nodeId));
  const flowEdges: Edge[] = [];
  const connectedPairs = new Set<string>();
  for (const placement of visiblePlacements) {
    const concept = placement.concept;
    const cluster = FEATURE_CLUSTERS.find((item) => item.id === placement.clusterId)!;
    const conceptNode = nodes.find((node) => node.id === placement.nodeId);
    const conceptPos = conceptNode?.position ?? center;
    const angle = Math.atan2(conceptPos.y - center.y, conceptPos.x - center.x);
    const hubSide = sideForAngle(angle);
    const conceptSide = SIDES.find((side) => side.id === hubSide)?.opposite ?? "bottom";
    flowEdges.push({
      id: `hub:${placement.nodeId}`, source: "mindmesh-hub", sourceHandle: hubSide, target: placement.nodeId, targetHandle: `target-${conceptSide}`, type: "default",
      style: { stroke: `${cluster.color}99`, strokeWidth: selectedId === concept.id ? 2.8 : 1.8 },
    });
    for (const edge of visibleEdges) {
      if (edge.source_type !== cluster.sourceType || (edge.source !== concept.id && edge.target !== concept.id)) continue;
      const pair = `${placement.nodeId}:${edge.source_id}`;
      if (connectedPairs.has(pair)) continue;
      connectedPairs.add(pair);
      const sourceNodeId = `source:${edge.source_id}`;
      const sourceNode = nodes.find((node) => node.id === sourceNodeId);
      if (!sourceNode) continue;
      const dx = sourceNode.position.x - conceptPos.x;
      const dy = sourceNode.position.y - conceptPos.y;
      const conceptHandle = sideForAngle(Math.atan2(dy, dx));
      const sourceHandle = SIDES.find((side) => side.id === conceptHandle)?.opposite ?? "top";
      flowEdges.push({
        id: `source-edge:${placement.nodeId}:${edge.source_id}`,
        source: placement.nodeId, sourceHandle: `source-${conceptHandle}`, target: sourceNodeId, targetHandle: `target-${sourceHandle}`, type: "default",
        label: selectedId === concept.id ? edge.label : undefined,
        labelStyle: { fontSize: 10, fill: "#806c59" }, labelBgStyle: { fill: "#fffaf3", fillOpacity: 0.96 }, labelBgPadding: [4, 2],
        style: { stroke: `${cluster.color}80`, strokeWidth: 1.4 },
      });
    }
  }
  for (const source of visibleSources) {
    if (visibleEdges.some((edge) => edge.source_id === source.source_id && (finalConceptIds.has(`concept:${clusterForType(edge.source_type)?.id}:${encodeURIComponent(edge.source)}`) || finalConceptIds.has(`concept:${clusterForType(edge.source_type)?.id}:${encodeURIComponent(edge.target)}`)))) continue;
    const sourceNode = nodes.find((node) => node.id === `source:${source.source_id}`);
    if (!sourceNode) continue;
    const angle = Math.atan2(sourceNode.position.y - center.y, sourceNode.position.x - center.x);
    const hubSide = sideForAngle(angle);
    const sourceSide = SIDES.find((side) => side.id === hubSide)?.opposite ?? "top";
    const cluster = clusterForType(source.source_type);
    if (!cluster) continue;
    flowEdges.push({ id: `hub-source:${source.source_id}`, source: "mindmesh-hub", sourceHandle: hubSide, target: `source:${source.source_id}`, targetHandle: `target-${sourceSide}`, type: "default", style: { stroke: `${cluster.color}80`, strokeWidth: 1.4, strokeDasharray: "5 5" } });
  }
  return {
    nodes, edges: flowEdges, concepts, conceptPlacements: visiblePlacements, sources: visibleSources, allSourceCount: eligibleSources.length,
    hiddenConceptCount: Math.max(0, graph.nodes.length - concepts.length), hiddenSourceCount: Math.max(0, eligibleSources.length - visibleSources.length),
    clusterCounts: Object.fromEntries(FEATURE_CLUSTERS.map((cluster) => [cluster.id, (clusterConcepts.get(cluster.id)?.length ?? 0) + (clusterSources.get(cluster.id)?.length ?? 0)])) as Record<string, number>,
  };
}

function OrbitCanvas({ graph, sources, isFetching, refetch }: { graph: GraphData; sources: SourceItem[]; isFetching: boolean; refetch: () => void }) {
  const { fitView } = useReactFlow();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [positionOverrides, setPositionOverrides] = useState<PositionOverrides>({});
  const [liveNodes, setLiveNodes, onNodesChange] = useNodesState<OrbitalNodeData>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildMessage, setRebuildMessage] = useState("");
  const model = useMemo(() => buildOrbitalGraph(graph, sources, filter, query, selectedId, positionOverrides), [graph, sources, filter, query, selectedId, positionOverrides]);
  useEffect(() => { setLiveNodes(model.nodes); }, [model.nodes, setLiveNodes]);
  const handleDragStop = useCallback((_event: React.MouseEvent, node: Node<OrbitalNodeData>) => {
    setPositionOverrides((previous) => ({ ...previous, [node.id]: node.position }));
    setIsDragging(false);
  }, []);
  const handleDragStart = useCallback(() => setIsDragging(true), []);
  const selectedConcept = model.concepts.find((concept) => concept.id === selectedId);
  const selectedSource = selectedId?.startsWith("source:") ? model.sources.find((source) => source.source_id === selectedId.slice(7)) : undefined;
  const linkedSources = selectedConcept
    ? model.sources.filter((source) => graph.edges.some((edge) => edge.source_id === source.source_id && (edge.source === selectedConcept.id || edge.target === selectedConcept.id)))
    : selectedSource ? [selectedSource] : [];
  const filters = ["all", ...FEATURE_CLUSTERS.filter((cluster) => sources.some((source) => source.source_type === cluster.sourceType)).map((cluster) => cluster.sourceType)];
  const handleRebuild = async () => {
    setIsRebuilding(true);
    setRebuildMessage("Rebuilding source links… this can take a little while.");
    try {
      const result = await rebuildGraph();
      refetch();
      const issueCount = result.failures.length + result.sources_without_text;
      setRebuildMessage(`Rebuilt ${result.sources_rebuilt} of ${result.sources_seen} sources and linked ${result.relationships} relationships${issueCount ? ` · ${issueCount} source${issueCount === 1 ? "" : "s"} need attention` : ""}.`);
    } catch (error) {
      setRebuildMessage(error instanceof Error ? `Could not rebuild graph links: ${error.message}` : "Could not rebuild graph links. Try again.");
    } finally {
      setIsRebuilding(false);
    }
  };

  return (
    <>
      <div className="mb-4 flex flex-col gap-3 rounded-2xl border-2 border-ink bg-card p-3 shadow-brut sm:flex-row sm:items-center">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border-2 border-border bg-surface px-3 py-2.5 focus-within:border-brand"><Search className="h-4 w-4 shrink-0 text-muted" /><input value={query} onChange={(event) => { setQuery(event.target.value); setSelectedId(null); }} placeholder="Find a concept or saved source…" className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-muted" aria-label="Find a concept or saved source" />{query && <button aria-label="Clear search" onClick={() => setQuery("")}>×</button>}</label>
        <div className="flex flex-wrap gap-2">{filters.map((type) => <button key={type} onClick={() => { setFilter(type); setSelectedId(null); }} className={`rounded-lg border-2 border-ink px-3 py-2 text-xs font-semibold ${filter === type ? "bg-brand text-ink" : "bg-surface"}`}>{type === "all" ? "All sources" : SOURCE_LABELS[type] ?? type}</button>)}</div>
        <button onClick={refetch} disabled={isFetching || isRebuilding} aria-label="Refresh graph" className="inline-flex items-center justify-center gap-2 rounded-lg border-2 border-ink bg-card px-3 py-2 text-sm font-semibold hover:bg-surface disabled:opacity-60"><RefreshCw size={15} className={isFetching ? "animate-spin" : ""} /><span className="sm:hidden">Refresh</span></button>
        {!cloudMode && <button onClick={() => void handleRebuild()} disabled={isRebuilding} className="inline-flex items-center justify-center gap-2 rounded-lg border-2 border-ink bg-brand px-3 py-2 text-sm font-semibold text-ink hover:brightness-95 disabled:opacity-60"><RefreshCw size={15} className={isRebuilding ? "animate-spin" : ""} />{isRebuilding ? "Rebuilding…" : "Rebuild source links"}</button>}
      </div>
      {rebuildMessage && <p className="mb-3 text-xs text-muted" role="status">{rebuildMessage}</p>}

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted"><span><strong className="text-foreground">{model.concepts.length}</strong> concepts · <strong className="text-foreground">{model.sources.length}</strong> saved items · cluster size adapts to your library</span><div className="flex flex-wrap gap-x-4 gap-y-1">{FEATURE_CLUSTERS.filter((cluster) => model.clusterCounts[cluster.id] > 0).map((cluster) => <span key={cluster.id} className="inline-flex items-center gap-1.5"><i className="h-2.5 w-2.5 rounded-full" style={{ background: cluster.color }} />{cluster.label} · {model.clusterCounts[cluster.id]}</span>)}</div></div>

      <div className="orbital-shell">
        <div className={`orbital-stage${isDragging ? " is-dragging" : ""}`}>
          <ReactFlow nodes={liveNodes} edges={model.edges} onNodesChange={onNodesChange} nodeTypes={nodeTypes} onlyRenderVisibleElements onNodeClick={(_event, node) => { if (node.data.kind !== "brand" && node.type !== "cluster") setSelectedId(node.data.kind === "source" ? `source:${node.data.id}` : node.data.id); }} onNodeDragStart={handleDragStart} onNodeDragStop={handleDragStop} onPaneClick={() => setSelectedId(null)} fitView fitViewOptions={{ padding: 0.08, minZoom: 0.45, maxZoom: 0.94, duration: 350 }} minZoom={0.35} maxZoom={1.6} zoomOnScroll zoomOnPinch zoomOnDoubleClick={false} panOnDrag panOnScroll={false} nodesDraggable nodesConnectable={false} elementsSelectable proOptions={{ hideAttribution: true }}>
            <Background color="#eadfce" gap={28} size={1} />
            <Controls showFitView showInteractive={false} position="bottom-left" />
          </ReactFlow>
          <button onClick={() => { setPositionOverrides({}); requestAnimationFrame(() => void fitView({ padding: 0.08, duration: 350, minZoom: 0.35, maxZoom: 0.94 })); }} className="absolute bottom-3 right-3 z-10 rounded-lg border-2 border-ink bg-card px-3 py-2 text-xs font-semibold shadow-brut hover:bg-surface">Reset layout</button>
          {selectedId && <button onClick={() => setSelectedId(null)} className="absolute right-3 top-3 z-20 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-semibold shadow-elevated">Clear selection</button>}
        </div>
        <div className="orbital-mobile">
          <div className="orbital-mobile-hub"><Image src="/logo.png" alt="" width={48} height={48} /><span><strong>MindMesh</strong><small>Your connected knowledge</small></span></div>
          <div className="orbital-mobile-branch" aria-hidden="true" />
          {FEATURE_CLUSTERS.map((cluster) => {
            const clusterConcepts = model.conceptPlacements.filter((placement) => placement.clusterId === cluster.id);
            const clusterSources = model.sources.filter((source) => clusterForType(source.source_type)?.id === cluster.id);
            if (!clusterConcepts.length && !clusterSources.length) return null;
            return <section key={cluster.id} className="orbital-mobile-cluster" style={{ "--cluster-color": cluster.color, "--cluster-tint": cluster.tint } as React.CSSProperties}>
              <h3><i />{cluster.label}<small>{clusterConcepts.length + clusterSources.length}</small></h3>
              {clusterConcepts.map(({ concept, nodeId }) => <button key={nodeId} onClick={() => setSelectedId(concept.id)} className={`orbital-mobile-concept${selectedId === concept.id ? " is-active" : ""}`}><Brain size={17} /><span><strong>{cleanLabel(concept.label)}</strong><small>{concept.count} mentions</small></span><ArrowUpRight size={15} /></button>)}
              <div className="orbital-mobile-sources">{clusterSources.map((source) => <div key={source.source_id} className={`orbital-mobile-source${selectedId === `source:${source.source_id}` ? " is-active" : ""}`}>
            <a className="orbital-mobile-thumb" href={originalSourceUrl(source)} target={originalSourceUrl(source) ? "_blank" : undefined} rel="noopener noreferrer" aria-label="Open original saved content" onClick={(event) => event.stopPropagation()}>{source.thumbnail ? <img src={source.thumbnail} alt={source.title ? `Thumbnail for ${source.title}` : "Saved source thumbnail"} loading="lazy" onError={(event) => { event.currentTarget.style.display = "none"; event.currentTarget.parentElement?.classList.add("thumbnail-failed"); }} /> : <SourceFallback type={source.source_type} />}{source.thumbnail && <span className="thumbnail-fallback"><SourceFallback type={source.source_type} /></span>}<span className="mobile-open-hint"><ExternalLink size={11} /></span></a>
            <button onClick={() => setSelectedId(`source:${source.source_id}`)} className="orbital-mobile-source-copy"><strong>{source.title || source.file_name || "Untitled source"}</strong><small>{SOURCE_LABELS[source.source_type] ?? source.source_type}</small></button>
              </div>)}</div>
            </section>;
          })}
        </div>
        <div className="orbital-legend">{FEATURE_CLUSTERS.filter((cluster) => model.clusterCounts[cluster.id] > 0).map((cluster) => <span key={cluster.id}><i className="legend-dot" style={{ background: cluster.color }} />{cluster.label}</span>)}<span>Click thumbnails to open original content · drag to rearrange</span></div>
        {(model.hiddenConceptCount > 0 || model.hiddenSourceCount > 0) && <p className="px-4 pb-3 text-center text-xs text-muted">Showing the {model.concepts.length} most connected concepts and {model.sources.length} related sources to keep every thumbnail readable. Search to focus the graph.</p>}
      </div>

      {(selectedConcept || selectedSource) && <section className="mt-4 rounded-2xl border-2 border-ink bg-card p-4 shadow-brut" aria-live="polite">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-[11px] font-bold uppercase tracking-[0.16em] text-brand">{selectedConcept ? "Selected concept" : SOURCE_LABELS[selectedSource?.source_type ?? ""] ?? "Saved source"}</p><h2 className="mt-1 text-xl font-extrabold">{selectedConcept ? cleanLabel(selectedConcept.label) : selectedSource?.title || selectedSource?.file_name || "Saved source"}</h2><p className="mt-1 text-sm text-muted">{selectedConcept ? `${selectedConcept.count} mentions · ${linkedSources.length} connected saved source${linkedSources.length === 1 ? "" : "s"}` : selectedSource?.summary || "Open the original item or continue exploring its connected ideas."}</p></div><div className="flex gap-2"><Link href={`/chat?q=${encodeURIComponent(selectedConcept ? cleanLabel(selectedConcept.label) : selectedSource?.title ?? "")}`} className="rounded-lg border-2 border-ink bg-surface px-3 py-2 text-sm font-semibold">Ask AI</Link>{selectedSource && originalSourceUrl(selectedSource) && <a href={originalSourceUrl(selectedSource)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-lg border-2 border-ink bg-brand px-3 py-2 text-sm font-semibold text-ink">Open source <ExternalLink size={14} /></a>}</div></div>
        {linkedSources.length > 0 && <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{linkedSources.map((source) => <a key={source.source_id} href={originalSourceUrl(source)} target={originalSourceUrl(source) ? "_blank" : undefined} rel="noreferrer" className="flex items-center gap-3 rounded-xl border border-border bg-surface p-2.5 transition hover:border-brand"><span className="h-16 w-24 shrink-0 overflow-hidden rounded-lg bg-card">{source.thumbnail ? <img src={source.thumbnail} alt={source.title ? `Thumbnail for ${source.title}` : "Saved source thumbnail"} className="h-full w-full object-cover" /> : <SourceFallback type={source.source_type} />}</span><span className="min-w-0"><strong className="line-clamp-2 text-xs">{source.title || source.file_name || "Untitled source"}</strong><small className="mt-1 block text-muted">{SOURCE_LABELS[source.source_type] ?? source.source_type}</small></span><ArrowUpRight size={14} className="ml-auto shrink-0" /></a>)}</div>}
      </section>}
    </>
  );
}

function KnowledgeGraphPage() {
  const graphQuery = useQuery({ queryKey: ["knowledge-graph"], queryFn: getGraph, staleTime: 5_000, refetchInterval: 10_000, refetchIntervalInBackground: false });
  const sourcesQuery = useQuery({ queryKey: ["knowledge-graph-sources"], queryFn: () => listSources(undefined, 1, 100), staleTime: 5_000, refetchInterval: 10_000, refetchIntervalInBackground: false });
  const isLoading = graphQuery.isLoading || sourcesQuery.isLoading;
  const isError = graphQuery.isError || sourcesQuery.isError;
  const error = graphQuery.error || sourcesQuery.error;
  const refetch = () => { void graphQuery.refetch(); void sourcesQuery.refetch(); };
  return (
    <div className="mx-auto max-w-[1800px]">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3"><div><div className="mb-1 flex items-center gap-2 text-brand"><Network className="h-5 w-5" /><span className="text-xs font-bold uppercase tracking-[0.18em]">Your connected knowledge</span></div><h1 className="text-3xl font-extrabold tracking-tight sm:text-4xl">Knowledge Graph</h1><p className="mt-1 max-w-2xl text-sm text-muted">Your MindMesh at the center. Explore how ideas connect to everything you have saved.</p></div>{!isLoading && graphQuery.data && graphQuery.data.nodes.length > 0 && <button onClick={refetch} disabled={graphQuery.isFetching || sourcesQuery.isFetching} className="inline-flex items-center gap-2 rounded-lg border-2 border-ink bg-card px-3 py-2 text-sm font-semibold hover:bg-surface disabled:opacity-60"><RefreshCw size={15} className={graphQuery.isFetching || sourcesQuery.isFetching ? "animate-spin" : ""} />Refresh graph</button>}</div>
      {isLoading ? <div className="grid min-h-[560px] place-items-center rounded-2xl border-2 border-ink bg-card"><div className="text-center"><Network className="mx-auto mb-3 h-8 w-8 animate-pulse text-brand" /><p className="text-sm font-medium">Building your orbital knowledge map…</p></div></div>
        : isError ? <div className="rounded-2xl border-2 border-red-500/50 bg-red-500/5 p-6 text-sm"><div className="flex items-center gap-2 font-semibold text-red-600"><AlertCircle className="h-4 w-4" />Couldn’t load your knowledge graph</div><p className="mt-2 text-muted">{error instanceof Error ? error.message : "The graph service is temporarily unavailable."}</p><button onClick={refetch} className="mt-4 rounded-lg border-2 border-ink bg-card px-3 py-2 font-semibold">Try again</button></div>
        : graphQuery.data && sourcesQuery.data ? graphQuery.data.nodes.length === 0 && sourcesQuery.data.items.length === 0 ? <div className="grid min-h-[560px] place-items-center rounded-2xl border-2 border-ink bg-card p-8 text-center shadow-brut"><div className="max-w-md"><span className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl border-2 border-ink bg-brand text-ink"><Image src="/logo.png" alt="MindMesh" width={52} height={52} /></span><h2 className="text-xl font-bold">Your knowledge orbit starts with a saved source</h2><p className="mt-2 text-sm text-muted">Save a YouTube video or Instagram post. MindMesh will connect its ideas and show its thumbnail here.</p><div className="mt-5 flex justify-center gap-2"><Link className="brut-btn rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-ink" href="/youtube">Add YouTube</Link><Link className="rounded-lg border-2 border-ink bg-surface px-4 py-2 text-sm font-semibold" href="/instagram">Add Instagram</Link></div></div></div> : <ReactFlowProvider><OrbitCanvas graph={graphQuery.data} sources={sourcesQuery.data.items} isFetching={graphQuery.isFetching || sourcesQuery.isFetching} refetch={refetch} /></ReactFlowProvider> : null}
    </div>
  );
}

export default KnowledgeGraphPage;
