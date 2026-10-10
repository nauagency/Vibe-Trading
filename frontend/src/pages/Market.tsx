import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Activity, AlertTriangle, BarChart3, CircleDollarSign, Flame, Layers3, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, type MarketDashboard, type MarketItem } from "@/lib/api";
import { cn } from "@/lib/utils";

const FILTERS = ["all", "crypto", "metals", "forex", "energy", "us-stock", "prediction"] as const;

function money(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);
}

function formatTime(value: string, locale: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-US", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function Market() {
  const { t, i18n } = useTranslation();
  const [selected, setSelected] = useState("all");
  const [data, setData] = useState<MarketDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (market: string) => {
    setLoading(true);
    setError(null);
    try { setData(await api.getMarket(market)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : t("market.error")); }
    finally { setLoading(false); }
  }, [t]);

  useEffect(() => { void load(selected); }, [load, selected]);
  const itemCounts = useMemo(() => data?.items.reduce((result, item) => {
    result[item.kind] = (result[item.kind] ?? 0) + 1;
    return result;
  }, {} as Record<string, number>) ?? {}, [data]);

  return (
    <div className="min-h-screen p-4 sm:p-6 lg:p-8">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-6">
        <header className="flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-positive/30 bg-positive/5 px-3 py-1 text-xs text-positive">
              <ShieldCheck className="h-3.5 w-3.5" />{t("market.badge")}
            </div>
            <h1 className="text-3xl font-semibold tracking-tight">{t("market.title")}</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{t("market.subtitle")}</p>
          </div>
          <button type="button" onClick={() => void load(selected)} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-md border bg-card px-4 py-2 text-sm disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}{t("market.refresh")}
          </button>
        </header>

        {error && <div role="alert" className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger"><AlertTriangle className="mt-0.5 h-4 w-4" />{error}</div>}

        {data && <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric icon={<Activity className="h-4 w-4" />} label={t("market.signals")} value={String(itemCounts.position ?? 0)} />
            <Metric icon={<BarChart3 className="h-4 w-4" />} label={t("market.strategies")} value={String(itemCounts.strategy ?? 0)} />
            <Metric icon={<Layers3 className="h-4 w-4" />} label={t("market.positions")} value={String(data.account.open_positions)} />
            <Metric icon={<CircleDollarSign className="h-4 w-4" />} label={t("market.equity")} value={money(data.account.equity)} />
          </section>

          <div className="flex flex-wrap gap-2" aria-label={t("market.filtersLabel")}>
            {FILTERS.map((market) => <button key={market} type="button" onClick={() => setSelected(market)}
              className={cn("rounded-full border px-3 py-1.5 text-xs transition-colors", selected === market ? "border-primary bg-primary/10 font-medium text-primary" : "bg-card text-muted-foreground hover:text-foreground")}
            >{t(`market.filters.${market}`)} <span className="ms-1 opacity-70">{data.counts[market] ?? 0}</span></button>)}
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
            <section className="overflow-hidden rounded-xl border bg-card">
              <div className="border-b p-5"><h2 className="font-semibold">{t("market.feedTitle")}</h2><p className="mt-1 text-xs text-muted-foreground">{t("market.feedHint")}</p></div>
              {loading ? <div className="flex h-48 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
                : data.items.length ? <div className="divide-y">{data.items.map((item) => <FeedItem key={item.id} item={item} locale={i18n.language} />)}</div>
                : <div className="p-12 text-center"><p className="text-sm font-medium">{t("market.emptyTitle")}</p><p className="mt-2 text-xs text-muted-foreground">{t("market.emptyHint")}</p></div>}
            </section>

            <aside className="h-fit overflow-hidden rounded-xl border bg-card xl:sticky xl:top-6">
              <div className="flex items-center gap-2 border-b p-5"><Flame className="h-4 w-4 text-primary" /><div><h2 className="font-semibold">{t("market.trending")}</h2><p className="mt-1 text-xs text-muted-foreground">{t("market.trendingHint")}</p></div></div>
              <div className="divide-y">{data.trending.map((item, index) => <div key={`${item.market}-${item.symbol}`} className="flex items-center gap-3 p-4">
                <span className="w-5 text-xs text-muted-foreground">#{index + 1}</span>
                <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><span className="font-semibold">{item.symbol}</span><span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] text-primary"><MarketName market={item.market} /></span></div><p className="mt-1 text-xs text-muted-foreground">{t("market.trendStats", { events: item.event_count, signals: item.signal_count, positions: item.position_count })}</p></div>
                <span className="text-xs font-medium">{money(item.current_price)}</span>
              </div>)}</div>
            </aside>
          </div>

          <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" /><p><span className="font-medium">{t("market.safetyTitle")}</span> {t("market.safetyBody")}</p></div>
        </>}
      </div>
    </div>
  );
}

function FeedItem({ item, locale }: { item: MarketItem; locale: string }) {
  const { t } = useTranslation();
  return <article className="p-5"><div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] uppercase text-primary">{t(`market.kinds.${item.kind}`)}</span><h3 className="font-medium">{item.title}</h3></div>{item.content && <p className="mt-2 line-clamp-3 whitespace-pre-line text-sm leading-6 text-muted-foreground">{item.content}</p>}<div className="mt-3 flex flex-wrap gap-1.5">{item.symbols.map((symbol) => <span key={symbol} className="rounded-md border px-2 py-1 text-xs font-medium">{symbol}</span>)}{item.side && <span className="rounded-md border px-2 py-1 text-xs uppercase">{item.side}</span>}{item.quantity != null && <span className="rounded-md border px-2 py-1 text-xs">{t("market.quantity")}: {item.quantity}</span>}{item.price != null && <span className="rounded-md border px-2 py-1 text-xs">{money(item.price)}</span>}{item.pnl != null && <span className={cn("rounded-md border px-2 py-1 text-xs", item.pnl >= 0 ? "text-positive" : "text-danger")}>P&amp;L {money(item.pnl)}</span>}</div></div><div className="shrink-0 text-xs text-muted-foreground">{formatTime(item.created_at, locale)}</div></div></article>;
}

function MarketName({ market }: { market: string }) {
  const { t } = useTranslation();
  if (market === "all") return t("market.filters.all");
  if (market === "crypto") return t("market.filters.crypto");
  if (market === "metals") return t("market.filters.metals");
  if (market === "forex") return t("market.filters.forex");
  if (market === "energy") return t("market.filters.energy");
  if (market === "us-stock") return t("market.filters.us-stock");
  if (market === "prediction") return t("market.filters.prediction");
  return market;
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="rounded-xl border bg-card p-5"><div className="flex items-center justify-between text-xs text-muted-foreground"><span>{label}</span>{icon}</div><div className="mt-3 text-2xl font-semibold tracking-tight">{value}</div></div>;
}
