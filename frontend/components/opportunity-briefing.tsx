"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  FileSearch,
  LoaderCircle,
  RefreshCw,
  Sparkles,
  TriangleAlert,
} from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type SourceDocument = { name: string; url: string };
type IngestedDocument = {
  id: number;
  file_name: string;
  source_url: string;
  status: "pending" | "ready" | "failed";
  page_count: number;
  character_count: number;
  error_message?: string;
  chunk_count?: number;
};
type Analysis = {
  id: number;
  analysis_type: string;
  content: string;
  sources: { label: string; title: string; url?: string }[];
  updated_at: string;
};
type BriefingPayload = {
  documents: IngestedDocument[];
  analyses: Analysis[];
};

const analysisTypes = [
  ["executive_summary", "Executive briefing"],
  ["requirements", "Requirements"],
  ["risks", "Risk assessment"],
  ["bid_no_bid", "Bid / no-bid"],
  ["compliance_matrix", "Compliance matrix"],
  ["amendment_comparison", "Compare amendments"],
] as const;

function titleFor(type: string) {
  return (
    analysisTypes.find((row) => row[0] === type)?.[1] ??
    type.replaceAll("_", " ")
  );
}

export function OpportunityBriefing({
  noticeId,
  sourceDocuments,
  opportunity,
}: {
  noticeId: string;
  sourceDocuments: SourceDocument[];
  opportunity: Record<string, unknown>;
}) {
  const [payload, setPayload] = useState<BriefingPayload>({
    documents: [],
    analyses: [],
  });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [answerSources, setAnswerSources] = useState<
    { label: string; title: string; url?: string }[]
  >([]);

  const briefingUrl = `/ai/opportunities/${encodeURIComponent(noticeId)}/briefing/`;

  const load = useCallback(async () => {
    try {
      const result = await apiGet<BriefingPayload>(briefingUrl);
      setPayload(result);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Briefing could not be loaded",
      );
    }
  }, [briefingUrl]);

  useEffect(() => {
    let cancelled = false;

    apiGet<BriefingPayload>(briefingUrl)
      .then((result) => {
        if (!cancelled) {
          setPayload(result);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Briefing could not be loaded",
          );
        }
      });

    return () => {
      cancelled = true;
    };
  }, [briefingUrl]);

  const ready = useMemo(
    () => payload.documents.filter((row) => row.status === "ready").length,
    [payload.documents],
  );

  async function ingest() {
    setBusy("ingest");
    setMessage("");
    try {
      await apiPost(
        `/ai/opportunities/${encodeURIComponent(noticeId)}/documents/`,
        { documents: sourceDocuments, opportunity },
      );
      await load();
      setMessage("Government documents were securely ingested and indexed.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Documents could not be ingested",
      );
    } finally {
      setBusy("");
    }
  }

  async function analyze(type: string, refresh = false) {
    setBusy(type);
    setMessage("");
    try {
      const result = await apiPost<Analysis>(briefingUrl, {
        analysis_type: type,
        refresh,
      });
      setPayload((current) => ({
        documents: current.documents,
        analyses: [
          result,
          ...current.analyses.filter((row) => row.analysis_type !== type),
        ],
      }));
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Analysis could not be generated",
      );
    } finally {
      setBusy("");
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    if (!question.trim()) return;

    setBusy("ask");
    setAnswer("");
    try {
      const result = await apiPost<{
        answer: string;
        sources?: { label: string; title: string; url?: string }[];
      }>(`/ai/opportunities/${encodeURIComponent(noticeId)}/ask/`, {
        message: question,
      });
      setAnswer(result.answer);
      setAnswerSources(result.sources ?? []);
    } catch (error) {
      setAnswer(error instanceof Error ? error.message : "ForgeAI could not answer");
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="forgeai-briefing-shell">
      <div className="data-panel forgeai-ingestion-panel">
        <div className="panel-title-row">
          <div>
            <span className="eyebrow">FORGEAI DOCUMENT INTELLIGENCE</span>
            <h2>Opportunity briefing</h2>
            <p>
              Answers and reports are grounded in text extracted from authorized
              solicitation files.
            </p>
          </div>
          <Sparkles />
        </div>

        <div className="insight-strip">
          <div>
            <span>Source files</span>
            <strong>{sourceDocuments.length}</strong>
          </div>
          <div>
            <span>Indexed</span>
            <strong>{ready}</strong>
          </div>
          <div>
            <span>Analyses</span>
            <strong>{payload.analyses.length}</strong>
          </div>
        </div>

        <button
          className="primary-button"
          onClick={() => void ingest()}
          disabled={busy !== "" || !sourceDocuments.length}
        >
          {busy === "ingest" ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <FileSearch size={16} />
          )}{" "}
          {payload.documents.length
            ? "Re-index documents"
            : "Ingest government documents"}
        </button>

        {message && <p className="inline-message">{message}</p>}

        <div className="forgeai-document-status">
          {payload.documents.map((document) => (
            <article key={document.id} className={document.status}>
              <span>
                {document.status === "ready" ? (
                  <CheckCircle2 />
                ) : document.status === "failed" ? (
                  <TriangleAlert />
                ) : (
                  <LoaderCircle />
                )}
              </span>
              <div>
                <strong>{document.file_name}</strong>
                <small>
                  {document.status === "ready"
                    ? `${document.page_count || "—"} pages · ${(
                        document.character_count || 0
                      ).toLocaleString()} characters · ${
                        document.chunk_count ?? 0
                      } passages`
                    : document.error_message || "Processing"}
                </small>
              </div>
            </article>
          ))}
        </div>
      </div>

      <div className="data-panel">
        <div className="panel-title-row">
          <div>
            <span className="eyebrow">ONE-CLICK ANALYSIS</span>
            <h2>Build capture intelligence</h2>
          </div>
        </div>

        <div className="ai-preset-row forgeai-analysis-actions">
          {analysisTypes.map(([type, label]) => (
            <button
              key={type}
              disabled={!ready || busy !== ""}
              onClick={() => void analyze(type)}
            >
              {busy === type ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <Sparkles size={15} />
              )}{" "}
              {label}
            </button>
          ))}
        </div>

        <form className="forgeai-question" onSubmit={ask}>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ask a question about the ingested solicitation documents…"
          />
          <button
            className="primary-button"
            disabled={!ready || busy !== "" || !question.trim()}
          >
            {busy === "ask" ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Sparkles size={16} />
            )}{" "}
            Ask documents
          </button>
        </form>

        {answer && (
          <article className="context-ai-answer">
            <h3>Document-grounded answer</h3>
            <div className="rich-description">{answer}</div>
            {answerSources.length > 0 && (
              <div className="ai-source-list contextual-source-list">
                <span>Sources</span>
                {answerSources.map((source) =>
                  source.url ? (
                    <a
                      key={source.label}
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <b>{source.label}</b>
                      {source.title}
                    </a>
                  ) : (
                    <div key={source.label}>
                      <b>{source.label}</b>
                      {source.title}
                    </div>
                  ),
                )}
              </div>
            )}
          </article>
        )}
      </div>

      <div className="forgeai-analysis-grid">
        {payload.analyses.map((analysis) => (
          <article className="data-panel" key={analysis.id}>
            <div className="panel-title-row">
              <div>
                <span className="eyebrow">
                  {titleFor(analysis.analysis_type)}
                </span>
                <h2>{titleFor(analysis.analysis_type)}</h2>
                <small>
                  Updated {new Date(analysis.updated_at).toLocaleString()}
                </small>
              </div>
              <button
                className="icon-button"
                title="Regenerate"
                onClick={() => void analyze(analysis.analysis_type, true)}
              >
                <RefreshCw size={16} />
              </button>
            </div>

            <div className="rich-description forgeai-analysis-content">
              {analysis.content}
            </div>

            {analysis.sources?.length > 0 && (
              <div className="ai-source-list contextual-source-list">
                <span>Document citations</span>
                {analysis.sources.slice(0, 20).map((source) => (
                  <a
                    key={`${analysis.id}-${source.label}`}
                    href={source.url || "#"}
                    target={source.url ? "_blank" : undefined}
                    rel={source.url ? "noreferrer" : undefined}
                  >
                    <b>{source.label}</b>
                    {source.title}
                  </a>
                ))}
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
