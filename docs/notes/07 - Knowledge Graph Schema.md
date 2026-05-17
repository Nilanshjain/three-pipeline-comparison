# 07 - Knowledge Graph Schema

> [!summary] One sentence
> TigerGraph stores 5 vertex types and the edges between them — Document, DocumentChunk, Entity, RelationshipType, Community. Each vertex carries metadata; each edge encodes a real relationship the LLM extracted.

The schema is defined in `infra/graphrag-upstream/common/gsql/supportai/SupportAI_Schema.gsql`. It's not arbitrary — every vertex and edge is there to enable specific retrieval patterns.

## Vertex types

### Document
- One per ingested article (we have 432)
- Attributes: `id`, `title`, `source`, `epoch_added`, `epoch_processed`
- Edge: `HAS_CHILD` → DocumentChunk

### DocumentChunk
- A piece of a Document (~600-1000 chars), chunked using the semantic chunker
- We have 6,943 chunks across 432 docs (avg ~16 chunks/doc)
- Attributes: `id`, `chunk_text`, `embedding` (1536-d Gemini vector), `chunk_index`, `epoch_processed`
- Edges:
  - `HAS_CHILD` ← Document (parent)
  - `CONTAINS_ENTITY` → Entity (every entity mentioned in this chunk)
  - `IS_AFTER` → DocumentChunk (sequential order within a document — for "what came next" queries)

### Entity
- An extracted person, place, concept, organization (e.g. `demis-hassabis`, `deepmind`, `transformer-architecture`)
- We have 190 entities (mostly good after our cleanup)
- Attributes: `id` (kebab-case name), `definition` (LLM-generated description), `epoch_processed`
- Edges:
  - `CONTAINS_ENTITY` ← DocumentChunk (which chunks mention this entity)
  - `RELATIONSHIP` → Entity (typed edges via RelationshipType — see below)
  - `IN_COMMUNITY` → Community

### RelationshipType
- The *type* of a relationship between two entities — `FOUNDED`, `WORKS_AT`, `DEVELOPED`, `IS_A`, etc.
- Reified as vertices (not just edge attributes) so they can be queried, embedded, and traversed
- Attributes: `id`, `definition`, `epoch_processed`

### Community
- A cluster of densely-interconnected entities, discovered by Louvain community detection
- We have 78 communities
- Attributes: `id`, `summary` (LLM-generated 1-paragraph topic description), `level`
- Hierarchical: communities can have parent communities (multiple levels of clustering)
- Edge: `IN_COMMUNITY` ← Entity

## Edge types in plain English

```
Document --HAS_CHILD--> DocumentChunk
DocumentChunk --IS_AFTER--> DocumentChunk        (next-chunk order)
DocumentChunk --CONTAINS_ENTITY--> Entity
Entity --RELATIONSHIP--> Entity                  (typed via RelationshipType)
Entity --IN_COMMUNITY--> Community
Community --IN_COMMUNITY--> Community            (parent community)
```

## Why this schema, not just "chunks + embeddings"?

Three things the schema enables that a flat chunk index can't:

1. **Multi-hop reasoning**: "Which OpenAI co-founder was previously a PhD student of Hinton?"
   - Vector search finds chunks about OpenAI founders and chunks about Hinton's students separately
   - **Graph traversal** finds Entity(`ilya-sutskever`) — connected to both `openai` (via FOUNDED) and `geoffrey-hinton` (via STUDENT_OF) — in a single hop

2. **Aggregate/synthesis questions**: "How does GraphRAG differ from Basic RAG?"
   - Vector search returns many chunks each describing one or the other
   - **Community summary** (level 1) might literally be titled "Retrieval Augmented Generation Techniques" with the comparison built in

3. **Provenance**: which chunks support a claim?
   - The graph maintains the `CONTAINS_ENTITY` edge, so you can trace any answer back to source documents

## A walkthrough — what happens to one chunk

Take `demis_hassabis.txt`. After ingestion + ECC processing:

1. **Document** vertex created: `{id: "demis_hassabis", title: "Demis Hassabis", ...}`
2. Chunker splits into ~14 chunks → **DocumentChunk** vertices: `demis_hassabis_chunk_0`, `_chunk_1`, ...
3. Each chunk gets embedded → 1536-d vector stored in the `embedding` attribute
4. **LLM-Entity-Extractor** reads chunk text, returns JSON like:
   ```json
   {
     "nodes": [
       {"id": "Demis Hassabis", "type": "person", "description": "British AI researcher..."},
       {"id": "DeepMind", "type": "organization", "description": "AI research lab..."}
     ],
     "rels": [
       {"source": "Demis Hassabis", "target": "DeepMind", "relation_type": "FOUNDED"}
     ]
   }
   ```
5. For each `node`: upsert an **Entity** vertex + `CONTAINS_ENTITY` edge from chunk to entity
6. For each `rel`: upsert a **RelationshipType** vertex (e.g., `FOUNDED`) + create `Entity --RELATIONSHIP--> Entity` edges threading through it
7. After all chunks are processed, **community detection** clusters entities, generates summaries

## Queries the schema unlocks (GSQL queries shipped by upstream)

In `infra/graphrag-upstream/common/gsql/supportai/`:

- `GraphRAG_Hybrid_Vector_Search.gsql` — the workhorse. Takes a query embedding, finds anchor chunks by cosine, traverses to entities and communities, returns the assembled context.
- `Get_Entity_Context.gsql` — given an entity, return all chunks that mention it (provenance).
- `Get_Community_Summary.gsql` — given a community, return its summary text.
- `Scan_For_Updates.gsql` — used by ECC to find unprocessed chunks.

## How retrieval actually uses the schema

For a query like "Who founded DeepMind?":

1. Query embedding hits the `embedding` index on DocumentChunk
2. Top-5 chunks come back (mostly `demis_hassabis_*`, `deepmind_*`)
3. From each, traverse `CONTAINS_ENTITY` → reach `demis-hassabis`, `deepmind`, `google-brain`, etc.
4. From `deepmind` entity, traverse `RELATIONSHIP` → find the `FOUNDED` rel back to `demis-hassabis`, `shane-legg`, `mustafa-suleyman`
5. Also traverse `IN_COMMUNITY` → find a community like "DeepMind and its founders" with a pre-computed summary
6. All of this lands in the final prompt as structured context

Without the graph, vector search returns chunks but no structural reasoning about who-founded-what.

## Real-world numbers

After everything ran:
- 432 Documents
- 6,943 DocumentChunks (avg ~16/doc)
- 190 Entities (about 8% of chunks contained an entity successfully extracted)
- 78 Communities

These numbers are low for the corpus size — see [[11 - Failures and Learnings]] for why (bad prompts, rate limits, partial extraction). A full extraction would yield ~2,000–5,000 entities. We made it work with 190 because the retriever degrades gracefully with sparse entities.

## Related

- [[06 - Pipeline 3 - GraphRAG]] — how the schema gets used at query time
- [[11 - Failures and Learnings]] — the bad-prompt era explains the entity gap
- [[08 - Embeddings Deep Dive]] — why 1536-d vectors

`#schema` `#tigergraph` `#knowledge-graph`
