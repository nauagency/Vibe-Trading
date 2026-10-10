import { Suspense, lazy, type ComponentType } from "react";
import { createBrowserRouter } from "react-router";
import { Layout } from "@/components/layout/Layout";

const Home = lazy(() => import("@/pages/Home").then((m) => ({ default: m.Home })));
const Agent = lazy(() => import("@/pages/Agent").then((m) => ({ default: m.Agent })));
const RunDetail = lazy(() =>
  import("@/pages/RunDetail").then((m) => ({ default: m.RunDetail })),
);
const Compare = lazy(() =>
  import("@/pages/Compare").then((m) => ({ default: m.Compare })),
);
const Settings = lazy(() =>
  import("@/pages/Settings").then((m) => ({ default: m.Settings })),
);
const Runtime = lazy(() =>
  import("@/pages/Runtime").then((m) => ({ default: m.Runtime })),
);
const Scheduled = lazy(() =>
  import("@/pages/Scheduled").then((m) => ({ default: m.Scheduled })),
);
const Reports = lazy(() =>
  import("@/pages/Reports").then((m) => ({ default: m.Reports })),
);
const Portfolio = lazy(() =>
  import("@/pages/Portfolio").then((m) => ({ default: m.Portfolio })),
);
const PaperTrading = lazy(() =>
  import("@/pages/PaperTrading").then((m) => ({ default: m.PaperTrading })),
);
const Market = lazy(() =>
  import("@/pages/Market").then((m) => ({ default: m.Market })),
);
const FinancialEvents = lazy(() =>
  import("@/pages/FinancialEvents").then((m) => ({ default: m.FinancialEvents })),
);
const TradingRoadmap = lazy(() =>
  import("@/pages/TradingRoadmap").then((m) => ({ default: m.TradingRoadmap })),
);
const Correlation = lazy(() =>
  import("@/pages/Correlation").then((m) => ({ default: m.Correlation })),
);
const AlphaZoo = lazy(() =>
  import("@/pages/AlphaZoo").then((m) => ({ default: m.AlphaZoo })),
);
const OptionsLab = lazy(() =>
  import("@/pages/OptionsLab").then((m) => ({ default: m.OptionsLab })),
);
const Leaderboard = lazy(() => import("@/pages/Community").then((m) => ({ default: m.Leaderboard })));
const Strategies = lazy(() => import("@/pages/Community").then((m) => ({ default: () => <m.CommunityFeed type="strategy" /> })));
const Discussions = lazy(() => import("@/pages/Community").then((m) => ({ default: () => <m.CommunityFeed type="discussion" /> })));
const Positions = lazy(() => import("@/pages/Community").then((m) => ({ default: m.Positions })));
const Trade = lazy(() => import("@/pages/Community").then((m) => ({ default: m.Trade })));
const Exchange = lazy(() => import("@/pages/Community").then((m) => ({ default: m.Exchange })));
const CopyTrading = lazy(() => import("@/pages/Community").then((m) => ({ default: m.CopyTrading })));
const Challenges = lazy(() => import("@/pages/Community").then((m) => ({ default: m.Challenges })));

function PageLoader() {
  return (
    <div className="flex h-[60vh] items-center justify-center text-muted-foreground">
      Loading…
    </div>
  );
}

function wrap(Component: ComponentType) {
  return (
    <Suspense fallback={<PageLoader />}>
      <Component />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: wrap(Agent) },
      { path: "/about", element: wrap(Home) },
      { path: "/agent", element: wrap(Agent) },
      { path: "/runtime", element: wrap(Runtime) },
      { path: "/scheduled", element: wrap(Scheduled) },
      { path: "/reports", element: wrap(Reports) },
      { path: "/portfolio", element: wrap(Portfolio) },
      { path: "/paper-trading", element: wrap(PaperTrading) },
      { path: "/market", element: wrap(Market) },
      { path: "/leaderboard", element: wrap(Leaderboard) },
      { path: "/challenges", element: wrap(Challenges) },
      { path: "/copy-trading", element: wrap(CopyTrading) },
      { path: "/strategies", element: wrap(Strategies) },
      { path: "/discussions", element: wrap(Discussions) },
      { path: "/positions", element: wrap(Positions) },
      { path: "/trade", element: wrap(Trade) },
      { path: "/exchange", element: wrap(Exchange) },
      { path: "/financial-events", element: wrap(FinancialEvents) },
      { path: "/roadmap", element: wrap(TradingRoadmap) },
      { path: "/settings", element: wrap(Settings) },
      { path: "/runs/:runId", element: wrap(RunDetail) },
      { path: "/compare", element: wrap(Compare) },
      { path: "/correlation", element: wrap(Correlation) },
      { path: "/options", element: wrap(OptionsLab) },
      { path: "/alpha-zoo", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/bench", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/compare", element: wrap(AlphaZoo) },
      { path: "/alpha-zoo/:alphaId", element: wrap(AlphaZoo) },
    ],
  },
]);
