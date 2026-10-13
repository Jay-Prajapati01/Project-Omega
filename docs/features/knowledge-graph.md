# Knowledge Graph

The `/graph` page turns indexed YouTube and Instagram sources into an interactive map. It is a source explorer, not a separate ingestion pipeline.

## Data and source ownership

The backend stores extracted concepts and relationships with their originating `source_id`, `source_type`, and title. The frontend places concepts into a platform cluster only when both the edge's source ID and platform match a saved source. A concept can appear in both clusters when it is genuinely present in sources from both platforms; each appearance remains tied to its platform-specific source edges.

The graph centers the MindMesh brand node, lays out separate YouTube and Instagram clusters, sizes a cluster based on the concepts and saved sources it contains, and draws smooth relationships. Source cards use the saved thumbnail when available, with a provider fallback image when not. Clicking a source thumbnail opens the original YouTube or Instagram URL. Concepts, sources, and graph controls support selection, filtering, dragging, and fit/zoom interactions.

## Older saved sources

Sources saved before source-platform metadata was attached to graph relationships may not have correct cluster membership. Rebuild using the graph refresh/rebuild control (API: `POST /api/graph/rebuild`). The backend re-reads saved sources and their indexed chunks, regenerates or falls back to source metadata, and writes source-tagged relationships. If a source has no indexed chunks or usable metadata, it can remain visible in Stored while contributing no concept edges.

## Troubleshooting

- **A YouTube concept appears under Instagram:** refresh the graph first. If legacy edges are present, rebuild the graph so relationships are reattached using each source's platform metadata.
- **A cluster is empty:** verify that the source completed ingestion and has indexed text/chunks, then rebuild.
- **A thumbnail is missing:** the graph uses a platform fallback when the provider supplied no thumbnail. Private or removed source links may no longer open.
- **A source opens at an unexpected URL:** check that its saved `source_type` and `source_id` agree; graph source cards derive their provider URL from those saved identifiers.
