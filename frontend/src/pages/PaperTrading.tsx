import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router";
import {
  AlertTriangle,
  CircleDollarSign,
  FlaskConical,
  Layers3,
  Loader2,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api, type PaperTradingDashboard } from "@/lib/api";

function money(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function number(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 6 }).format(value);
}

export function PaperTrading() {
  const { t } = useTranslation();
  const [data, setData] = useState<PaperTradingDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await api.getPaperTrading());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("paperTrading.error"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const activeCandidates = useMemo(
    () => data?.strategies.filter((strategy) =>
      strategy.tags.some((tag) => ["paper-only", "paper_candidate"].includes(tag.toLowerCase())),
    ) ?? [],
    [data],
  );

  return (
    <div className="min-h-screen p-4 sm:p-6 lg:p-8">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-6">
        <header className="flex flex-col gap-4 border-b pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-positive/30 bg-positive/5 px-3 py-1 text-xs text-positive">
              <ShieldCheck className="h-3.5 w-3.5" />
              {t("paperTrading.badge")}
            </div>
            <h1 className="text-3xl font-semibold tracking-tight">{t("paperTrading.title")}</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">{t("paperTrading.subtitle")}</p>
          </div>
          <button onClick={() => void load()} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-md border bg-card px-4 py-2 text-sm disabled:opacity-50">
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            {t("paperTrading.refresh")}
          </button>
        </header>

        {error ? <div className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 p-4 text-sm text-danger"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{error}</span></div> : null}
        {loading && !data ? <div className="flex h-56 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div> : null}

        {data ? <>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric icon={<CircleDollarSign className="h-4 w-4" />} label={t("paperTrading.cash")} value={money(data.account.cash)} />
            <Metric icon={<TrendingUp className="h-4 w-4" />} label={t("paperTrading.equity")} value={money(data.account.equity)} />
            <Metric icon={<Layers3 className="h-4 w-4" />} label={t("paperTrading.positions")} value={String(data.positions.length)} />
            <Metric icon={<FlaskConical className="h-4 w-4" />} label={t("paperTrading.candidates")} value={String(activeCandidates.length)} />
          </section>

          <section className="overflow-hidden rounded-xl border bg-card">
            <div className="flex flex-col gap-2 border-b p-5 sm:flex-row sm:items-center sm:justify-between">
              <div><h2 className="font-semibold">{t("paperTrading.strategyTitle")}</h2><p className="mt-1 text-xs text-muted-foreground">{t("paperTrading.strategyHint")}</p></div>
              <Link to="/reports" className="text-sm font-medium text-primary hover:underline">{t("paperTrading.openReports")}</Link>
            </div>
            <div className="divide-y">
              {data.strategies.length ? data.strategies.map((strategy) => <article key={strategy.signal_id} className="p-5">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="font-medium">{strategy.title}</h3><span className="rounded-full bg-muted px-2 py-0.5 text-[11px] uppercase text-muted-foreground">{strategy.source}</span></div><p className="mt-2 line-clamp-3 whitespace-pre-line text-sm leading-6 text-muted-foreground">{strategy.content}</p></div>
                  <div className="flex shrink-0 flex-wrap gap-1.5">{strategy.symbols.map((symbol) => <span key={symbol} className="rounded-md border px-2 py-1 text-xs font-medium">{symbol}</span>)}</div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">{strategy.tags.slice(0, 7).map((tag) => <span key={tag} className="rounded-full bg-primary/5 px-2 py-1 text-[11px] text-primary">{tag}</span>)}</div>
              </article>) : <div className="p-10 text-center text-sm text-muted-foreground">{t("paperTrading.noStrategies")}</div>}
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border bg-card">
            <div className="border-b p-5"><h2 className="font-semibold">{t("paperTrading.positionTitle")}</h2><p className="mt-1 text-xs text-muted-foreground">{t("paperTrading.positionHint")}</p></div>
            {data.positions.length ? <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-sm"><thead className="bg-muted/40 text-left text-xs text-muted-foreground"><tr><Th>{t("paperTrading.symbol")}</Th><Th>{t("paperTrading.side")}</Th><Th>{t("paperTrading.quantity")}</Th><Th>{t("paperTrading.entry")}</Th><Th>{t("paperTrading.current")}</Th><Th>{t("paperTrading.pnl")}</Th></tr></thead><tbody className="divide-y">{data.positions.map((position, index) => <tr key={`${position.symbol}-${position.opened_at}-${index}`}><Td><div className="font-medium">{position.symbol}</div><div className="text-xs text-muted-foreground">{position.market}</div></Td><Td><span className={position.side === "long" ? "text-positive" : "text-danger"}>{position.side.toUpperCase()}</span></Td><Td>{number(position.quantity)}</Td><Td>{number(position.entry_price)}</Td><Td>{number(position.current_price)}</Td><Td><span className={(position.unrealized_pnl ?? 0) >= 0 ? "text-positive" : "text-danger"}>{money(position.unrealized_pnl)}</span></Td></tr>)}</tbody></table></div> : <div className="p-10 text-center"><p className="text-sm font-medium">{t("paperTrading.noPositions")}</p><p className="mt-2 text-xs text-muted-foreground">{t("paperTrading.noPositionsHint")}</p></div>}
          </section>

          <div className="flex items-start gap-2 rounded-lg border border-warning/30 bg-warning/5 p-4 text-sm"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" /><p><span className="font-medium">{t("paperTrading.safetyTitle")}</span> {t("paperTrading.safetyBody")}</p></div>
        </> : null}
      </div>
    </div>
  );
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="rounded-xl border bg-card p-5"><div className="flex items-center justify-between text-xs text-muted-foreground"><span>{label}</span>{icon}</div><div className="mt-3 text-2xl font-semibold tracking-tight">{value}</div></div>;
}

function Th({ children }: { children: ReactNode }) { return <th className="px-4 py-3 font-medium">{children}</th>; }
function Td({ children }: { children: ReactNode }) { return <td className="px-4 py-3">{children}</td>; }
