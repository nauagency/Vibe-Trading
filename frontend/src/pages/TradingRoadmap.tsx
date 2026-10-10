import { Link } from "react-router";
import { ArrowRight, BarChart3, Bot, CheckCircle2, Database, FlaskConical, Lightbulb, LockKeyhole, ShieldCheck, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";

const steps = [
  { key: "idea", icon: Lightbulb, to: "/", status: "ready" },
  { key: "data", icon: Database, to: "/settings#data-sources", status: "ready" },
  { key: "backtest", icon: BarChart3, to: "/reports", status: "ready" },
  { key: "validation", icon: ShieldCheck, to: "/reports", status: "ready" },
  { key: "approval", icon: CheckCircle2, to: "/paper-trading", status: "ready" },
  { key: "paper", icon: FlaskConical, to: "/paper-trading", status: "ready" },
  { key: "review", icon: TrendingUp, to: "/paper-trading", status: "ready" },
  { key: "live", icon: LockKeyhole, to: "/runtime", status: "locked" },
] as const;

export function TradingRoadmap() {
  const { t } = useTranslation();
  return <div className="min-h-screen p-4 sm:p-6 lg:p-8"><div className="mx-auto w-full max-w-[1200px]">
    <header className="border-b pb-6"><div className="mb-3 inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground"><Bot className="h-3.5 w-3.5 text-primary" />{t("roadmap.badge")}</div><h1 className="text-3xl font-semibold tracking-tight">{t("roadmap.title")}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">{t("roadmap.subtitle")}</p></header>
    <section className="mt-6 grid gap-3 lg:grid-cols-2">{steps.map((step, index) => { const Icon=step.icon; return <div key={step.key} className={`relative rounded-xl border bg-card p-5 ${step.status === "locked" ? "border-warning/30" : ""}`}><div className="flex items-start gap-4"><div className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg ${step.status === "locked" ? "bg-warning/10 text-warning" : "bg-primary/10 text-primary"}`}><Icon className="h-5 w-5" /></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="text-xs font-medium text-muted-foreground">{String(index+1).padStart(2,"0")}</span><h2 className="font-semibold">{t(`roadmap.steps.${step.key}.title`)}</h2>{step.status === "locked" ? <span className="rounded-full bg-warning/10 px-2 py-0.5 text-[11px] text-warning">{t("roadmap.locked")}</span> : null}</div><p className="mt-2 text-sm leading-6 text-muted-foreground">{t(`roadmap.steps.${step.key}.description`)}</p><div className="mt-3 rounded-md bg-muted/40 p-3 text-xs"><span className="font-medium">{t("roadmap.gate")}: </span><span className="text-muted-foreground">{t(`roadmap.steps.${step.key}.gate`)}</span></div><Link to={step.to} className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">{t(`roadmap.steps.${step.key}.action`)}<ArrowRight className="h-3.5 w-3.5" /></Link></div></div></div>; })}</section>
    <section className="mt-6 rounded-xl border border-warning/30 bg-warning/5 p-5"><div className="flex items-start gap-3"><LockKeyhole className="mt-0.5 h-5 w-5 shrink-0 text-warning" /><div><h2 className="font-semibold">{t("roadmap.safetyTitle")}</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">{t("roadmap.safetyBody")}</p></div></div></section>
  </div></div>;
}
