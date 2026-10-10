import { Activity, BarChart3, Bot, CalendarClock, CandlestickChart, ClipboardCopy, FileText, Flame, FlaskConical, Gift, Layers, Map, MessageCircle, Newspaper, Settings, Swords, Trophy, WalletCards } from "lucide-react";

export const NAVIGATION_GROUPS = [
  { id: "research", items: [
    { id: "roadmap", to: "/roadmap", icon: Map },
    { id: "agent", to: "/", icon: Bot },
    { id: "reports", to: "/reports", icon: FileText },
    { id: "financialEvents", to: "/financial-events", icon: Newspaper },
    { id: "market", to: "/market", icon: Flame },
    { id: "leaderboard", to: "/leaderboard", icon: Trophy },
    { id: "challenges", to: "/challenges", icon: Swords },
    { id: "copyTrading", to: "/copy-trading", icon: ClipboardCopy },
    { id: "strategies", to: "/strategies", icon: BarChart3 },
    { id: "discussions", to: "/discussions", icon: MessageCircle },
    { id: "positions", to: "/positions", icon: WalletCards },
    { id: "trade", to: "/trade", icon: CandlestickChart },
    { id: "exchange", to: "/exchange", icon: Gift },
    { id: "paperTrading", to: "/paper-trading", icon: FlaskConical },
    { id: "portfolio", to: "/portfolio", icon: WalletCards },
  ] },
  { id: "analysis", items: [
    { id: "alphaZoo", to: "/alpha-zoo", icon: Layers },
    { id: "optionsLab", to: "/options", icon: CandlestickChart },
    { id: "correlation", to: "/correlation", icon: BarChart3 },
  ] },
  { id: "automation", items: [
    { id: "scheduled", to: "/scheduled", icon: CalendarClock },
    { id: "runtime", to: "/runtime", icon: Activity },
    { id: "settings", to: "/settings", icon: Settings },
  ] },
] as const;

export type NavigationItem = typeof NAVIGATION_GROUPS[number]["items"][number];

export function isNavigationActive(to: string, pathname: string): boolean {
  return to === "/" ? pathname === "/" || pathname === "/agent"
    : pathname === to || pathname.startsWith(`${to}/`);
}
