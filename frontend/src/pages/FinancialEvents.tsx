import { useEffect, useState } from "react";
import { AlertTriangle, ExternalLink, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, type FinancialEventFeed, type FinancialEventsDashboard } from "@/lib/api";

function formatTime(value: string, locale: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function FinancialEvents() {
  const { t, i18n } = useTranslation();
  const locale: "vi" | "en" = i18n.resolvedLanguage?.toLowerCase().startsWith("vi") ? "vi" : "en";
  const [data, setData] = useState<FinancialEventsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await api.getFinancialEvents(locale));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("financialEvents.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [locale]);

  const sectionTitles: Record<string, string> = {
    "macro-signals": t("financialEvents.sections.macro-signals"),
    "etf-flows": t("financialEvents.sections.etf-flows"),
    "featured-stocks": t("financialEvents.sections.featured-stocks"),
    "financial-news": t("financialEvents.sections.financial-news"),
  };

  return <div className="min-h-screen p-4 sm:p-6 lg:p-8">
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-6">
      <header className="flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-positive/30 bg-positive/5 px-3 py-1 text-xs text-positive">
            <ShieldCheck className="h-3.5 w-3.5" />{t("financialEvents.badge")}
          </div>
          <h1 className="text-3xl font-semibold tracking-tight">{t("financialEvents.title")}</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{t("financialEvents.subtitle")}</p>
        </div>
        <button onClick={() => void load()} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-md border bg-card px-4 py-2 text-sm disabled:opacity-50">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}{t("financialEvents.refresh")}
        </button>
      </header>

      {error ? <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div> : null}
      {loading && !data ? <div className="flex h-56 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div> : null}

      {data ? <>
        <div><h2 className="text-xl font-semibold">{t("financialEvents.originalTitle")}</h2><p className="mt-1 text-sm text-muted-foreground">{t("financialEvents.originalHint")}</p></div>
        <EventGrid feeds={data.sections} title={(feed) => sectionTitles[feed.id] ?? feed.label} />

        <div className="mt-2"><h2 className="text-xl font-semibold">{t("financialEvents.assetsTitle")}</h2><p className="mt-1 text-sm text-muted-foreground">{t("financialEvents.assetsHint")}</p></div>
        <EventGrid feeds={data.assets} />

        <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" /><p>{t("financialEvents.disclaimer")}</p></div>
      </> : null}
    </div>
  </div>;
}

function EventGrid({ feeds, title }: { feeds: FinancialEventFeed[]; title?: (feed: FinancialEventFeed) => string }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.resolvedLanguage?.toLowerCase().startsWith("vi") ? "vi-VN" : "en-US";
  return <section className="grid gap-4 xl:grid-cols-2">
    {feeds.map((feed) => <article key={feed.id} className="overflow-hidden rounded-xl border bg-card">
      <div className="flex items-center justify-between border-b p-5"><h2 className="font-semibold">{title ? title(feed) : feed.label}</h2><span className="text-xs text-muted-foreground">{t("financialEvents.itemCount", { count: feed.items.length })}</span></div>
      <div className="divide-y">
        {feed.items.length ? feed.items.map((item, index) => <a key={`${item.url}-${index}`} href={item.url} target="_blank" rel="noreferrer" className="block p-5 transition-colors hover:bg-muted/30">
          <div className="flex items-start justify-between gap-3"><div><div className="mb-1 flex flex-wrap gap-1.5">{item.source === "Forex Factory" ? <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">{t("financialEvents.prioritySource")}</span> : null}{item.country ? <span className="rounded-full bg-muted px-2 py-0.5 text-[10px]">{item.country}</span> : null}{item.impact ? <span className="rounded-full bg-warning/10 px-2 py-0.5 text-[10px] text-warning">{t(`financialEvents.impact.${item.impact.toLowerCase()}`, { defaultValue: item.impact })}</span> : null}</div><h3 className="font-medium leading-6">{item.title}</h3></div><ExternalLink className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" /></div>
          <div className="mt-2 flex flex-wrap gap-x-3 text-xs text-muted-foreground"><span>{item.source || t("financialEvents.unknownSource")}</span><span>{formatTime(item.published, locale)}</span></div>
          {item.summary ? <p className="mt-2 text-xs text-muted-foreground">{item.summary}</p> : null}
        </a>) : <div className="p-8 text-center text-sm text-muted-foreground">{feed.available ? t("financialEvents.noItems") : t("financialEvents.unavailable")}</div>}
      </div>
    </article>)}
  </section>;
}
