"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Award,
  Building2,
  FileSearch,
  FolderKanban,
  Search,
  Target,
  Users,
} from "lucide-react";
import { apiGet } from "@/lib/api";

type Hit = {
  type: string;
  id: string | number;
  title: string;
  subtitle: string;
  href: string;
  group: string;
  metadata?: Record<string, unknown>;
};

type SearchResponse = {
  query: string;
  results: Hit[];
  groups: Record<string, number>;
};

const icons: Record<string, typeof Search> = {
  Opportunities: FileSearch,
  Capture: Target,
  Work: Target,
  Collaboration: FolderKanban,
  Documents: FileSearch,
  Network: Users,
  "Market Intelligence": Building2,
  Awards: Award,
};

export default function UnifiedSearchPage() {
  const params = useSearchParams();
  const initial = params.get("q") ?? "";
  const [query, setQuery] = useState(initial);
  const [submitted, setSubmitted] = useState(initial);
  const [data, setData] = useState<SearchResponse>({
    query: "",
    results: [],
    groups: {},
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (submitted.trim().length < 2) {
      return;
    }

    let cancelled = false;

    Promise.resolve().then(() => {
      if (cancelled) {
        return;
      }

      setLoading(true);
      setError("");

      void apiGet<SearchResponse>(
        `/intelligence/search/?q=${encodeURIComponent(submitted)}&limit=12`,
      )
        .then((result) => {
          if (!cancelled) {
            setData(result);
          }
        })
        .catch((requestError: unknown) => {
          if (!cancelled) {
            setError(
              requestError instanceof Error
                ? requestError.message
                : "Search failed",
            );
          }
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
          }
        });
    });

    return () => {
      cancelled = true;
    };
  }, [submitted]);

  const grouped = useMemo(
    () =>
      data.results.reduce<Record<string, Hit[]>>((accumulator, row) => {
        (accumulator[row.group] ??= []).push(row);
        return accumulator;
      }, {}),
    [data.results],
  );

  function run(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();

    if (value.length < 2) {
      setData({ query: value, results: [], groups: {} });
      setError("");
    }

    setSubmitted(value);
    window.history.replaceState(
      null,
      "",
      value ? `/search?q=${encodeURIComponent(value)}` : "/search",
    );
  }

  return (
    <div className="page-stack unified-search-page">
      <section className="page-hero">
        <div>
          <span className="eyebrow">UNIFIED SEARCH</span>
          <h1>Find anything in ForgeGov.</h1>
          <p>
            Search live intelligence and your authorized workspace records without
            jumping between modules.
          </p>
        </div>
      </section>

      <form className="unified-search-box" onSubmit={run}>
        <Search size={22} />
        <input
          autoFocus
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Opportunity, solicitation, task, Project Room, document, company, award..."
        />
        <button type="submit">Search</button>
      </form>

      {error && <div className="network-message">{error}</div>}

      {loading ? (
        <div className="search-empty">Searching across ForgeGov…</div>
      ) : submitted.length < 2 ? (
        <div className="search-empty">
          <Search />
          <b>Start with at least two characters.</b>
          <span>Results respect your organization and Project Room permissions.</span>
        </div>
      ) : data.results.length === 0 ? (
        <div className="search-empty">
          <Search />
          <b>No matching records found.</b>
          <span>
            Try a solicitation number, company, agency, capability, task, or
            document name.
          </span>
        </div>
      ) : (
        <div className="unified-search-layout">
          <aside>
            <b>Result types</b>
            {Object.entries(data.groups).map(([group, count]) => (
              <a href={`#${group.replaceAll(" ", "-")}`} key={group}>
                <span>{group}</span>
                <strong>{count}</strong>
              </a>
            ))}
          </aside>

          <main>
            {Object.entries(grouped).map(([group, rows]) => {
              const Icon = icons[group] ?? Search;

              return (
                <section id={group.replaceAll(" ", "-")} key={group}>
                  <header>
                    <Icon size={19} />
                    <h2>{group}</h2>
                    <span>{rows.length}</span>
                  </header>

                  {rows.map((row) => (
                    <Link
                      href={row.href}
                      key={`${row.type}-${row.id}`}
                      className="unified-result"
                    >
                      <span className={`result-type type-${row.type}`}>
                        {row.type.replaceAll("_", " ")}
                      </span>
                      <div>
                        <b>{row.title}</b>
                        <small>{row.subtitle || "Open in ForgeGov"}</small>
                      </div>
                      <span>Open →</span>
                    </Link>
                  ))}
                </section>
              );
            })}
          </main>
        </div>
      )}
    </div>
  );
}
