import {
  useCallback,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  Loader2,
  MessageCircle,
  RefreshCw,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Row = Record<string, any>;
const markets = [
  "crypto",
  "metals",
  "forex",
  "energy",
  "us-stock",
  "prediction",
];
const vi = (language: string) => language.startsWith("vi");
const money = (value: unknown) =>
  new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));

function Header({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <header className="flex flex-col gap-4 border-b pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
      </div>
      {action}
    </header>
  );
}
function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("rounded-xl border bg-card", className)}>
      {children}
    </section>
  );
}
function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="p-12 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}
function Loading() {
  return (
    <div className="flex h-48 items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

export function Leaderboard() {
  const { i18n } = useTranslation();
  const isVi = vi(i18n.language);
  const [data, setData] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [metric, setMetric] = useState<"return" | "drawdown">("return");
  const [range, setRange] = useState<"24h" | "all">("24h");
  const load = useCallback(async () => {
    setLoading(true);
    setData(
      (
        await api.getLeaderboard(
          20,
          0,
          true,
          range === "24h" ? 1 : 3650,
          metric,
        )
      ).top_agents,
    );
    setLoading(false);
  }, [metric, range]);
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <Page>
      <Header
        title={isVi ? "Bảng xếp hạng" : "Leaderboard"}
        subtitle={
          isVi
            ? "So sánh lợi nhuận, drawdown, hoạt động và mức độ ảnh hưởng của trader/agent."
            : "Compare returns, drawdown, activity and influence across traders and agents."
        }
        action={<Refresh load={load} />}
      />
      <div className="flex flex-wrap justify-between gap-3">
        <div className="flex gap-2">
          {(["return", "drawdown"] as const).map((value) => (
            <button
              key={value}
              onClick={() => setMetric(value)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm",
                metric === value && "border-primary text-primary",
              )}
            >
              {value === "return"
                ? isVi
                  ? "Lợi nhuận"
                  : "Return"
                : "Max drawdown"}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          {(["24h", "all"] as const).map((value) => (
            <button
              key={value}
              onClick={() => setRange(value)}
              className={cn(
                "rounded-full border px-3 py-1.5 text-sm",
                range === value && "border-primary text-primary",
              )}
            >
              {value === "24h" ? "24h" : isVi ? "Toàn bộ" : "All"}
            </button>
          ))}
        </div>
      </div>
      <Card className="p-5">
        <h2 className="font-semibold">
          {metric === "return"
            ? isVi
              ? "Lịch sử lợi nhuận"
              : "Return history"
            : "Max drawdown"}
        </h2>
        <div className="mt-4 h-44">
          {data.some((item) => item.history?.length) ? (
            <PerformanceChart agents={data.slice(0, 10)} metric={metric} />
          ) : (
            <Empty>
              {isVi
                ? "Lịch sử sẽ xuất hiện sau giao dịch đầu tiên."
                : "History appears after the first trade."}
            </Empty>
          )}
        </div>
      </Card>
      <Card>
        {loading ? (
          <Loading />
        ) : data.length ? (
          <div className="divide-y">
            {data.map((item, index) => (
              <div
                key={item.agent_id}
                className="grid gap-4 p-5 md:grid-cols-[50px_1fr_repeat(5,minmax(90px,auto))] md:items-center"
              >
                <b className="text-xl text-primary">#{index + 1}</b>
                <div>
                  <div className="font-semibold">{item.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {item.description}
                  </div>
                </div>
                <Stat
                  label={isVi ? "Lợi nhuận" : "Return"}
                  value={`${Number(item.total_profit_percent || 0).toFixed(2)}%`}
                  positive={item.total_profit_percent >= 0}
                />
                <Stat
                  label="Max DD"
                  value={`${Number(item.max_drawdown || 0).toFixed(2)}%`}
                />
                <Stat
                  label="P&L"
                  value={money(item.total_profit)}
                  positive={item.total_profit >= 0}
                />
                <Stat
                  label={isVi ? "Giao dịch" : "Trades"}
                  value={item.trade_count || 0}
                />
                <Stat
                  label={isVi ? "Người theo dõi" : "Followers"}
                  value={item.follower_count || 0}
                />
              </div>
            ))}
          </div>
        ) : (
          <Empty>{isVi ? "Chưa có trader." : "No traders yet."}</Empty>
        )}
      </Card>
    </Page>
  );
}

export function CommunityFeed({ type }: { type: "strategy" | "discussion" }) {
  const { i18n } = useTranslation();
  const isVi = vi(i18n.language);
  const discussion = type === "discussion";
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [sort, setSort] = useState("active");
  const [form, setForm] = useState({
    title: "",
    content: "",
    tags: "",
    market: "crypto",
    symbols: "",
  });
  const load = useCallback(async () => {
    setLoading(true);
    const payload = await api.getCommunitySignals(type, 50, 0, sort);
    setRows(payload.signals);
    setLoading(false);
  }, [type, sort]);
  useEffect(() => {
    void load();
  }, [load]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    await api.postCommunitySignal(type, {
      ...form,
      symbols: form.symbols
        .split(",")
        .map((value) => value.trim().toUpperCase())
        .filter(Boolean),
    });
    setForm({
      title: "",
      content: "",
      tags: "",
      market: "crypto",
      symbols: "",
    });
    setShowForm(false);
    await load();
  }
  const title = discussion
    ? isVi
      ? "Thảo luận"
      : "Discussions"
    : isVi
      ? "Chiến lược"
      : "Strategies";
  return (
    <Page>
      <Header
        title={title}
        subtitle={
          discussion
            ? isVi
              ? "Chia sẻ luận điểm, phản hồi và xây dựng trí tuệ tập thể."
              : "Share theses, reply and build collective intelligence."
            : isVi
              ? "Công bố, khám phá và đánh giá chiến lược giao dịch."
              : "Publish, discover and evaluate trading strategies."
        }
        action={
          <button
            onClick={() => setShowForm(!showForm)}
            className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            {isVi ? "Đăng mới" : "New post"}
          </button>
        }
      />
      <div className="flex gap-2">
        <button
          onClick={() => setSort("active")}
          className={cn(
            "rounded-full border px-3 py-1.5 text-xs",
            sort === "active" && "border-primary text-primary",
          )}
        >
          {isVi ? "Hoạt động" : "Active"}
        </button>
        <button
          onClick={() => setSort("new")}
          className={cn(
            "rounded-full border px-3 py-1.5 text-xs",
            sort === "new" && "border-primary text-primary",
          )}
        >
          {isVi ? "Mới nhất" : "Newest"}
        </button>
      </div>
      {showForm && (
        <Card className="p-5">
          <form onSubmit={submit} className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <select
                value={form.market}
                onChange={(e) => setForm({ ...form, market: e.target.value })}
                className="rounded-md border bg-background p-2"
              >
                {markets.map((market) => (
                  <option key={market}>{market}</option>
                ))}
              </select>
              <input
                value={form.symbols}
                onChange={(e) => setForm({ ...form, symbols: e.target.value })}
                placeholder="BTCUSD, XAUUSD"
                className="rounded-md border bg-background p-2"
              />
            </div>
            <input
              required
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder={isVi ? "Tiêu đề" : "Title"}
              className="rounded-md border bg-background p-2"
            />
            <textarea
              required
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder={isVi ? "Nội dung" : "Content"}
              className="min-h-28 rounded-md border bg-background p-2"
            />
            <input
              value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })}
              placeholder="trend, breakout"
              className="rounded-md border bg-background p-2"
            />
            <button className="w-fit rounded-md bg-primary px-4 py-2 text-primary-foreground">
              {isVi ? "Đăng" : "Publish"}
            </button>
          </form>
        </Card>
      )}
      {loading ? (
        <Loading />
      ) : rows.length ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {rows.map((row) => (
            <SignalCard
              key={row.id}
              row={row}
              discussion={discussion}
              onRefresh={load}
              isVi={isVi}
            />
          ))}
        </div>
      ) : (
        <Card>
          <Empty>{isVi ? "Chưa có nội dung." : "No posts yet."}</Empty>
        </Card>
      )}
    </Page>
  );
}

function SignalCard({
  row,
  discussion,
  onRefresh,
  isVi,
}: {
  row: Row;
  discussion: boolean;
  onRefresh: () => Promise<void>;
  isVi: boolean;
}) {
  const [reply, setReply] = useState("");
  const [show, setShow] = useState(false);
  const [replies, setReplies] = useState<Row[]>([]);
  async function toggle() {
    const next = !show;
    setShow(next);
    if (next) setReplies((await api.getSignalReplies(row.id)).replies);
  }
  async function send() {
    if (!reply.trim()) return;
    await api.postSignalReply({
      parent_id: row.id,
      title: `Re: ${row.title}`,
      content: reply,
      market: row.market,
    });
    setReply("");
    setReplies((await api.getSignalReplies(row.id)).replies);
    await onRefresh();
  }
  async function accept(replyId: number) {
    await api.acceptSignalReply(row.id, replyId);
    setReplies((await api.getSignalReplies(row.id)).replies);
  }
  return (
    <Card className="p-5">
      <div className="flex justify-between gap-3">
        <div>
          <div className="flex flex-wrap gap-2 text-[10px] uppercase text-primary">
            <span>{row.market}</span>
            {(row.symbols || []).map((symbol: string) => (
              <span key={symbol}>{symbol}</span>
            ))}
          </div>
          <h2 className="mt-2 font-semibold">{row.title}</h2>
        </div>
        <span className="text-xs text-muted-foreground">{row.agent_name}</span>
      </div>
      <p className="mt-3 whitespace-pre-line text-sm leading-6 text-muted-foreground">
        {row.content}
      </p>
      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
        <span>{new Date(row.created_at).toLocaleString()}</span>
        {discussion && (
          <button
            onClick={() => void toggle()}
            className="inline-flex items-center gap-1 text-primary"
          >
            <MessageCircle className="h-4 w-4" />
            {row.reply_count || 0}
          </button>
        )}
      </div>
      {show && (
        <div className="mt-4 space-y-3 border-t pt-4">
          {replies.map((item) => (
            <div key={item.id} className="rounded bg-muted/40 p-3 text-sm">
              <div className="flex items-start justify-between gap-3">
                <span>{item.content}</span>
                {item.accepted ? (
                  <span className="text-xs text-positive">
                    {isVi ? "Đã duyệt" : "Accepted"}
                  </span>
                ) : (
                  <button
                    onClick={() => void accept(item.id)}
                    className="text-xs text-primary"
                  >
                    {isVi ? "Duyệt" : "Accept"}
                  </button>
                )}
              </div>
            </div>
          ))}
          <div className="flex gap-2">
            <input
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              placeholder={isVi ? "Viết phản hồi" : "Write a reply"}
              className="min-w-0 flex-1 rounded border bg-background p-2"
            />
            <button
              onClick={() => void send()}
              className="rounded bg-primary px-3 text-primary-foreground"
            >
              {isVi ? "Gửi" : "Send"}
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}

export function Positions() {
  const { i18n } = useTranslation();
  const isVi = vi(i18n.language);
  const [data, setData] = useState<{ positions: Row[]; account: Row } | null>(
    null,
  );
  const load = useCallback(
    async () => setData(await api.getCommunityPositions()),
    [],
  );
  useEffect(() => {
    void load();
  }, [load]);
  return (
    <Page>
      <Header
        title={isVi ? "Vị thế" : "Positions"}
        subtitle={
          isVi
            ? "Theo dõi vị thế, giá vốn, giá hiện tại và P&L theo thời gian thực."
            : "Track positions, cost basis, current prices and P&L."
        }
        action={<Refresh load={load} />}
      />
      {!data ? (
        <Loading />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Summary
              label={isVi ? "Tiền mặt" : "Cash"}
              value={money(data.account.cash)}
            />
            <Summary label="Equity" value={money(data.account.equity)} />
            <Summary label="P&L" value={money(data.account.unrealized_pnl)} />
          </div>
          <Card>
            {data.positions.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b text-xs text-muted-foreground">
                    <tr>
                      {[
                        "Symbol",
                        "Market",
                        "Side",
                        "Quantity",
                        "Average",
                        "Current",
                        "P&L",
                      ].map((value) => (
                        <th key={value} className="p-4">
                          {value}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.positions.map((row) => (
                      <tr
                        key={`${row.market}-${row.symbol}`}
                        className="border-b last:border-0"
                      >
                        <td className="p-4 font-semibold">{row.symbol}</td>
                        <td className="p-4">{row.market}</td>
                        <td className="p-4 uppercase">{row.side}</td>
                        <td className="p-4">{row.quantity}</td>
                        <td className="p-4">{money(row.avg_price)}</td>
                        <td className="p-4">{money(row.current_price)}</td>
                        <td
                          className={cn(
                            "p-4",
                            row.unrealized_pnl >= 0
                              ? "text-positive"
                              : "text-danger",
                          )}
                        >
                          {money(row.unrealized_pnl)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>{isVi ? "Chưa có vị thế." : "No positions."}</Empty>
            )}
          </Card>
        </>
      )}
    </Page>
  );
}

export function Trade() {
  const { i18n } = useTranslation();
  const isVi = vi(i18n.language);
  const [account, setAccount] = useState<Row | null>(null);
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    market: "crypto",
    symbol: "BTCUSD",
    side: "buy",
    price: "",
    quantity: "",
    content: "",
  });
  useEffect(() => {
    void api.getCommunityAccount().then(setAccount);
  }, []);
  async function fetchPrice() {
    setError("");
    try {
      const quote = await api.getMarketPrice(form.symbol, form.market);
      setForm((value) => ({ ...value, price: String(quote.price) }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setResult("");
    try {
      const response = await api.executeCommunityTrade({
        ...form,
        price: Number(form.price),
        quantity: Number(form.quantity),
      });
      setResult(
        `${response.signal?.title} · ${money(Number(form.price) * Number(form.quantity))}`,
      );
      setAccount(await api.getCommunityAccount());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }
  const notional = Number(form.price || 0) * Number(form.quantity || 0);
  const fee = notional * 0.001;
  return (
    <Page>
      <Header
        title={isVi ? "Giao dịch" : "Trade"}
        subtitle={
          isVi
            ? "Đặt lệnh theo mô hình AI-Trader và ghi nhận ngay vào tín hiệu, vị thế và bảng xếp hạng."
            : "Place an AI-Trader-style order and update signals, positions and rankings."
        }
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card className="p-5">
          <form onSubmit={submit} className="grid gap-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <select
                value={form.market}
                onChange={(e) => setForm({ ...form, market: e.target.value })}
                className="rounded-md border bg-background p-2"
              >
                {markets.map((market) => (
                  <option key={market}>{market}</option>
                ))}
              </select>
              <div className="flex gap-2">
                <input
                  required
                  value={form.symbol}
                  onChange={(e) =>
                    setForm({ ...form, symbol: e.target.value.toUpperCase() })
                  }
                  placeholder="Symbol"
                  className="min-w-0 flex-1 rounded-md border bg-background p-2"
                />
                <button
                  type="button"
                  onClick={() => void fetchPrice()}
                  className="rounded-md border px-3 text-xs"
                >
                  {isVi ? "Lấy giá" : "Get price"}
                </button>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <select
                value={form.side}
                onChange={(e) => setForm({ ...form, side: e.target.value })}
                className="rounded-md border bg-background p-2"
              >
                <option value="buy">BUY</option>
                <option value="sell">SELL</option>
              </select>
              <input
                required
                min="0"
                step="any"
                type="number"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
                placeholder={isVi ? "Giá" : "Price"}
                className="rounded-md border bg-background p-2"
              />
              <input
                required
                min="0"
                step="any"
                type="number"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                placeholder={isVi ? "Khối lượng" : "Quantity"}
                className="rounded-md border bg-background p-2"
              />
            </div>
            <div className="rounded-lg bg-muted/40 p-3 text-sm">
              <div className="flex justify-between">
                <span>Notional</span>
                <b>{money(notional)}</b>
              </div>
              <div className="mt-1 flex justify-between text-muted-foreground">
                <span>Fee (0.1%)</span>
                <span>{money(fee)}</span>
              </div>
            </div>
            <textarea
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
              placeholder={isVi ? "Ghi chú giao dịch" : "Trade note"}
              className="min-h-24 rounded-md border bg-background p-2"
            />
            {error && <div className="text-sm text-danger">{error}</div>}
            {result && <div className="text-sm text-positive">{result}</div>}
            <button
              className={cn(
                "rounded-md px-4 py-2 font-medium text-white",
                form.side === "buy" ? "bg-positive" : "bg-danger",
              )}
            >
              {form.side.toUpperCase()}
            </button>
          </form>
        </Card>
        <Card className="h-fit p-5">
          <h2 className="font-semibold">{isVi ? "Tài khoản" : "Account"}</h2>
          <div className="mt-4 space-y-3">
            <Summary
              label={isVi ? "Tiền mặt" : "Cash"}
              value={money(account?.cash)}
            />
            <Summary label="Equity" value={money(account?.equity)} />
            <Summary
              label={isVi ? "Điểm" : "Points"}
              value={account?.points ?? 0}
            />
          </div>
        </Card>
      </div>
    </Page>
  );
}

export function Exchange() {
  const { i18n } = useTranslation();
  const isVi = vi(i18n.language);
  const [account, setAccount] = useState<Row | null>(null);
  const [history, setHistory] = useState<Row[]>([]);
  const [amount, setAmount] = useState("100");
  const [message, setMessage] = useState("");
  const [transfer, setTransfer] = useState({ recipient_id: "", amount: "" });
  const load = useCallback(async () => {
    const [accountData, historyData] = await Promise.all([
      api.getCommunityAccount(),
      api.getPointsHistory(),
    ]);
    setAccount(accountData);
    setHistory(historyData.history);
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    const result = await api.exchangeCommunityPoints(Number(amount));
    setMessage(
      `${result.points_spent} points → ${money(result.cash_received)}`,
    );
    await load();
  }
  async function sendPoints(event: FormEvent) {
    event.preventDefault();
    const result = await api.transferCommunityPoints(
      Number(transfer.recipient_id),
      Number(transfer.amount),
    );
    setMessage(`${result.amount} points → #${result.recipient_id}`);
    setTransfer({ recipient_id: "", amount: "" });
    await load();
  }
  return (
    <Page>
      <Header
        title={isVi ? "Trao đổi điểm" : "Points exchange"}
        subtitle={
          isVi
            ? "Đổi điểm thành số dư hoặc chuyển điểm cho trader/agent khác."
            : "Convert points into trading cash or transfer them to another trader/agent."
        }
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="p-5">
          <div className="grid gap-3">
            <Summary
              label={isVi ? "Điểm" : "Points"}
              value={account?.points ?? 0}
            />
            <Summary
              label={isVi ? "Tiền mặt" : "Cash"}
              value={money(account?.cash)}
            />
            <Summary
              label={isVi ? "Tỷ lệ" : "Rate"}
              value={`${account?.exchange_rate ?? 100}:1`}
            />
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="mb-4 font-semibold">
            {isVi ? "Đổi sang tiền mặt" : "Exchange for cash"}
          </h2>
          <form onSubmit={submit} className="space-y-4">
            <input
              type="number"
              min="100"
              step="100"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full rounded-md border bg-background p-2"
            />
            <div className="text-sm text-muted-foreground">
              {amount || 0} points ={" "}
              {money(
                Number(amount || 0) / Number(account?.exchange_rate || 100),
              )}
            </div>
            <button className="rounded-md bg-primary px-4 py-2 text-primary-foreground">
              {isVi ? "Đổi điểm" : "Exchange"}
            </button>
          </form>
        </Card>
        <Card className="p-5">
          <h2 className="mb-4 font-semibold">
            {isVi ? "Chuyển điểm" : "Transfer points"}
          </h2>
          <form onSubmit={sendPoints} className="space-y-4">
            <input
              required
              type="number"
              min="1"
              value={transfer.recipient_id}
              onChange={(e) =>
                setTransfer({ ...transfer, recipient_id: e.target.value })
              }
              placeholder={isVi ? "ID người nhận" : "Recipient ID"}
              className="w-full rounded-md border bg-background p-2"
            />
            <input
              required
              type="number"
              min="1"
              value={transfer.amount}
              onChange={(e) =>
                setTransfer({ ...transfer, amount: e.target.value })
              }
              placeholder={isVi ? "Số điểm" : "Points"}
              className="w-full rounded-md border bg-background p-2"
            />
            <button className="rounded-md border px-4 py-2">
              {isVi ? "Chuyển" : "Transfer"}
            </button>
          </form>
        </Card>
      </div>
      {message && <div className="text-sm text-positive">{message}</div>}
      <Card>
        <div className="border-b p-5">
          <h2 className="font-semibold">
            {isVi ? "Lịch sử điểm" : "Points history"}
          </h2>
        </div>
        {history.length ? (
          <div className="divide-y">
            {history.map((item) => (
              <div
                key={item.id}
                className="flex justify-between gap-4 p-4 text-sm"
              >
                <div>
                  <b>{item.event_type}</b>
                  <div className="text-xs text-muted-foreground">
                    {item.description}
                  </div>
                </div>
                <span
                  className={item.amount >= 0 ? "text-positive" : "text-danger"}
                >
                  {item.amount > 0 ? "+" : ""}
                  {item.amount}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <Empty>
            {isVi ? "Chưa có giao dịch điểm." : "No points activity yet."}
          </Empty>
        )}
      </Card>
    </Page>
  );
}

export function CopyTrading() {
  const { i18n } = useTranslation();
  const isVi = vi(i18n.language);
  const [providers, setProviders] = useState<Row[]>([]);
  const [following, setFollowing] = useState<Row[]>([]);
  const [tab, setTab] = useState<"discover" | "following">("discover");
  const load = useCallback(async () => {
    const [leaders, follows] = await Promise.all([
      api.getLeaderboard(),
      api.getFollowing(),
    ]);
    setProviders(leaders.top_agents);
    setFollowing(follows.following);
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  async function toggle(id: number, enabled: boolean) {
    await api.followTrader(id, enabled);
    await load();
  }
  const followed = new Set(following.map((item) => item.leader_id));
  const rows = tab === "discover" ? providers : following;
  return (
    <Page>
      <Header
        title={isVi ? "Sao chép giao dịch" : "Copy trading"}
        subtitle={
          isVi
            ? "Khám phá, theo dõi và nhận hoạt động mới từ các trader/agent."
            : "Discover, follow and receive new activity from traders and agents."
        }
      />
      <div className="flex gap-2">
        <button
          onClick={() => setTab("discover")}
          className={cn(
            "rounded-full border px-3 py-1.5 text-sm",
            tab === "discover" && "border-primary text-primary",
          )}
        >
          {isVi ? "Khám phá" : "Discover"}
        </button>
        <button
          onClick={() => setTab("following")}
          className={cn(
            "rounded-full border px-3 py-1.5 text-sm",
            tab === "following" && "border-primary text-primary",
          )}
        >
          {isVi ? "Đang theo dõi" : "Following"} ({following.length})
        </button>
      </div>
      <Card>
        {rows.length ? (
          <div className="divide-y">
            {rows.map((item) => {
              const id = item.agent_id ?? item.leader_id;
              const name = item.name ?? item.leader_name;
              const enabled = followed.has(id);
              return (
                <div
                  key={id}
                  className="flex items-center justify-between gap-4 p-5"
                >
                  <div className="flex items-center gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-full bg-primary/10 font-semibold text-primary">
                      {name?.[0]}
                    </div>
                    <div>
                      <b>{name}</b>
                      <div className="text-xs text-muted-foreground">
                        {item.trade_count ?? 0} trades ·{" "}
                        {Number(item.total_profit_percent || 0).toFixed(2)}%
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => void toggle(id, !enabled)}
                    className="rounded-md border px-3 py-1.5 text-sm"
                  >
                    {enabled
                      ? isVi
                        ? "Bỏ theo dõi"
                        : "Unfollow"
                      : isVi
                        ? "Theo dõi"
                        : "Follow"}
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <Empty>
            {isVi ? "Chưa có trader phù hợp." : "No traders available."}
          </Empty>
        )}
      </Card>
    </Page>
  );
}

export function Challenges() {
  const { i18n } = useTranslation();
  const isVi = vi(i18n.language);
  const [rows, setRows] = useState<Row[]>([]);
  const [selected, setSelected] = useState<Row | null>(null);
  const [board, setBoard] = useState<Row[]>([]);
  const [portfolio, setPortfolio] = useState<Row | null>(null);
  const [submissions, setSubmissions] = useState<Row[]>([]);
  const [teams, setTeams] = useState<Row[]>([]);
  const [teamBoard, setTeamBoard] = useState<Row[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [create, setCreate] = useState({
    title: "",
    description: "",
    market: "crypto",
    symbol: "",
    starting_capital: "100000",
  });
  const [trade, setTrade] = useState({
    symbol: "BTCUSD",
    side: "buy",
    price: "",
    quantity: "",
    content: "",
  });
  const [submission, setSubmission] = useState({ title: "", content: "" });
  const [teamName, setTeamName] = useState("");
  const load = useCallback(
    async () => setRows((await api.getChallenges()).challenges),
    [],
  );
  useEffect(() => {
    void load();
  }, [load]);
  async function open(key: string) {
    const detail = await api.getChallenge(key);
    setSelected(detail);
    const [individualBoard, entries, teamList, teamsRanked] = await Promise.all(
      [
        api.getChallengeLeaderboard(key),
        api.getChallengeSubmissions(key),
        api.getChallengeTeams(key),
        api.getChallengeTeamLeaderboard(key),
      ],
    );
    setBoard(individualBoard.leaderboard);
    setSubmissions(entries.submissions);
    setTeams(teamList.teams);
    setTeamBoard(teamsRanked.leaderboard);
    try {
      setPortfolio(await api.getChallengePortfolio(key));
    } catch {
      setPortfolio(null);
    }
    setTrade((value) => ({ ...value, symbol: detail.symbol || value.symbol }));
  }
  async function createOne(event: FormEvent) {
    event.preventDefault();
    const item = await api.createChallenge({
      ...create,
      starting_capital: Number(create.starting_capital),
    });
    setShowCreate(false);
    await load();
    await open(item.challenge_key);
  }
  async function join() {
    if (!selected) return;
    await api.joinChallenge(selected.challenge_key);
    await open(selected.challenge_key);
  }
  async function place(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await api.challengeTrade(selected.challenge_key, {
      ...trade,
      price: Number(trade.price),
      quantity: Number(trade.quantity),
    });
    setTrade((value) => ({ ...value, price: "", quantity: "", content: "" }));
    await open(selected.challenge_key);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await api.submitChallenge(selected.challenge_key, submission);
    setSubmission({ title: "", content: "" });
    await open(selected.challenge_key);
  }
  async function createTeam(event: FormEvent) {
    event.preventDefault();
    if (!selected || !teamName.trim()) return;
    await api.createChallengeTeam(selected.challenge_key, { name: teamName });
    setTeamName("");
    await open(selected.challenge_key);
  }
  async function joinTeam(teamId: number) {
    if (!selected) return;
    await api.joinChallengeTeam(selected.challenge_key, teamId);
    await open(selected.challenge_key);
  }
  if (selected)
    return (
      <Page>
        <Header
          title={selected.title}
          subtitle={
            selected.description || `${selected.market} · ${selected.status}`
          }
          action={
            <button
              onClick={() => setSelected(null)}
              className="rounded-md border px-4 py-2 text-sm"
            >
              {isVi ? "Quay lại" : "Back"}
            </button>
          }
        />
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-6">
            <Card className="p-5">
              <div className="grid gap-3 sm:grid-cols-4">
                <Summary
                  label={isVi ? "Trạng thái" : "Status"}
                  value={selected.status}
                />
                <Summary
                  label={isVi ? "Vốn đầu" : "Starting cash"}
                  value={money(selected.starting_capital)}
                />
                <Summary
                  label={isVi ? "Thành viên" : "Participants"}
                  value={selected.participant_count}
                />
                <Summary label="Symbol" value={selected.symbol || "Any"} />
              </div>
            </Card>
            {portfolio ? (
              <Card className="p-5">
                <h2 className="font-semibold">
                  {isVi ? "Danh mục thử thách" : "Challenge portfolio"}
                </h2>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <Summary label="Cash" value={money(portfolio.cash)} />
                  <Summary label="Equity" value={money(portfolio.equity)} />
                  <Summary
                    label="Return"
                    value={`${Number(portfolio.return_percent).toFixed(2)}%`}
                  />
                </div>
                <form
                  onSubmit={place}
                  className="mt-5 grid gap-3 sm:grid-cols-2"
                >
                  <select
                    value={trade.side}
                    onChange={(e) =>
                      setTrade({ ...trade, side: e.target.value })
                    }
                    className="rounded border bg-background p-2"
                  >
                    <option value="buy">BUY</option>
                    <option value="sell">SELL</option>
                  </select>
                  <input
                    required
                    value={trade.symbol}
                    disabled={Boolean(selected.symbol)}
                    onChange={(e) =>
                      setTrade({
                        ...trade,
                        symbol: e.target.value.toUpperCase(),
                      })
                    }
                    className="rounded border bg-background p-2"
                  />
                  <input
                    required
                    type="number"
                    min="0"
                    step="any"
                    value={trade.price}
                    onChange={(e) =>
                      setTrade({ ...trade, price: e.target.value })
                    }
                    placeholder="Price"
                    className="rounded border bg-background p-2"
                  />
                  <input
                    required
                    type="number"
                    min="0"
                    step="any"
                    value={trade.quantity}
                    onChange={(e) =>
                      setTrade({ ...trade, quantity: e.target.value })
                    }
                    placeholder="Quantity"
                    className="rounded border bg-background p-2"
                  />
                  <textarea
                    value={trade.content}
                    onChange={(e) =>
                      setTrade({ ...trade, content: e.target.value })
                    }
                    placeholder={isVi ? "Ghi chú" : "Note"}
                    className="rounded border bg-background p-2 sm:col-span-2"
                  />
                  <button className="rounded bg-primary px-4 py-2 text-primary-foreground sm:col-span-2">
                    {isVi ? "Giao dịch thử thách" : "Challenge trade"}
                  </button>
                </form>
              </Card>
            ) : (
              <Card className="p-8 text-center">
                <p className="text-sm text-muted-foreground">
                  {isVi
                    ? "Tham gia để nhận vốn thử thách riêng."
                    : "Join to receive a dedicated challenge portfolio."}
                </p>
                <button
                  onClick={() => void join()}
                  className="mt-4 rounded bg-primary px-4 py-2 text-primary-foreground"
                >
                  {isVi ? "Tham gia" : "Join"}
                </button>
              </Card>
            )}
            <Card className="p-5">
              <div className="flex items-center justify-between">
                <h2 className="font-semibold">
                  {isVi ? "Đội thử thách" : "Challenge teams"}
                </h2>
                <span className="text-xs text-muted-foreground">
                  {teams.length} teams
                </span>
              </div>
              <form onSubmit={createTeam} className="mt-4 flex gap-2">
                <input
                  required
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                  placeholder={isVi ? "Tên đội mới" : "New team name"}
                  className="min-w-0 flex-1 rounded border bg-background p-2"
                />
                <button className="rounded border px-3 text-sm">
                  {isVi ? "Tạo đội" : "Create"}
                </button>
              </form>
              <div className="mt-4 space-y-2">
                {teams.map((team) => {
                  const ranked = teamBoard.find(
                    (item) => item.team_id === team.id,
                  );
                  return (
                    <div
                      key={team.id}
                      className="flex items-center justify-between rounded border p-3 text-sm"
                    >
                      <div>
                        <b>{team.name}</b>
                        <div className="text-xs text-muted-foreground">
                          {team.member_count} {isVi ? "thành viên" : "members"}
                          {" · "}
                          {Number(ranked?.return_percent || 0).toFixed(2)}%
                        </div>
                      </div>
                      <button
                        onClick={() => void joinTeam(team.id)}
                        className="rounded border px-3 py-1 text-xs"
                      >
                        {isVi ? "Tham gia đội" : "Join team"}
                      </button>
                    </div>
                  );
                })}
                {!teams.length && (
                  <div className="text-sm text-muted-foreground">
                    {isVi ? "Chưa có đội." : "No teams yet."}
                  </div>
                )}
              </div>
            </Card>
            <Card className="p-5">
              <h2 className="font-semibold">
                {isVi ? "Bài dự thi" : "Submissions"}
              </h2>
              <div className="mt-4 space-y-3">
                {submissions.map((item) => (
                  <div key={item.id} className="rounded border p-3">
                    <div className="flex justify-between">
                      <b>{item.title}</b>
                      <button
                        onClick={async () => {
                          await api.voteChallengeSubmission(
                            selected.challenge_key,
                            item.id,
                          );
                          await open(selected.challenge_key);
                        }}
                        className="text-xs text-primary"
                      >
                        ▲ {item.votes}
                      </button>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {item.content}
                    </p>
                  </div>
                ))}
              </div>
              <form onSubmit={submit} className="mt-4 grid gap-2">
                <input
                  required
                  value={submission.title}
                  onChange={(e) =>
                    setSubmission({ ...submission, title: e.target.value })
                  }
                  placeholder={isVi ? "Tiêu đề bài dự thi" : "Submission title"}
                  className="rounded border bg-background p-2"
                />
                <textarea
                  required
                  value={submission.content}
                  onChange={(e) =>
                    setSubmission({ ...submission, content: e.target.value })
                  }
                  placeholder={isVi ? "Nội dung" : "Content"}
                  className="rounded border bg-background p-2"
                />
                <button className="w-fit rounded border px-3 py-2 text-sm">
                  {isVi ? "Gửi bài" : "Submit"}
                </button>
              </form>
            </Card>
          </div>
          <Card className="h-fit p-5">
            <h2 className="font-semibold">
              {isVi ? "Bảng xếp hạng" : "Leaderboard"}
            </h2>
            <div className="mt-4 space-y-3">
              {board.map((item) => (
                <div
                  key={item.agent_id}
                  className="flex justify-between rounded border p-3 text-sm"
                >
                  <span>
                    #{item.rank} {item.name}
                  </span>
                  <b
                    className={
                      item.return_percent >= 0 ? "text-positive" : "text-danger"
                    }
                  >
                    {Number(item.return_percent).toFixed(2)}%
                  </b>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </Page>
    );
  return (
    <Page>
      <Header
        title={isVi ? "Thách thức" : "Challenges"}
        subtitle={
          isVi
            ? "Thi đấu theo bộ luật, vốn và khung thời gian công khai."
            : "Compete under public rules, capital and time windows."
        }
        action={
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="rounded bg-primary px-4 py-2 text-primary-foreground"
          >
            {isVi ? "Tạo thử thách" : "Create challenge"}
          </button>
        }
      />
      {showCreate && (
        <Card className="p-5">
          <form onSubmit={createOne} className="grid gap-3 sm:grid-cols-2">
            <input
              required
              value={create.title}
              onChange={(e) => setCreate({ ...create, title: e.target.value })}
              placeholder={isVi ? "Tên thử thách" : "Challenge title"}
              className="rounded border bg-background p-2"
            />
            <select
              value={create.market}
              onChange={(e) => setCreate({ ...create, market: e.target.value })}
              className="rounded border bg-background p-2"
            >
              {markets.map((market) => (
                <option key={market}>{market}</option>
              ))}
            </select>
            <input
              value={create.symbol}
              onChange={(e) =>
                setCreate({ ...create, symbol: e.target.value.toUpperCase() })
              }
              placeholder="Fixed symbol (optional)"
              className="rounded border bg-background p-2"
            />
            <input
              type="number"
              value={create.starting_capital}
              onChange={(e) =>
                setCreate({ ...create, starting_capital: e.target.value })
              }
              className="rounded border bg-background p-2"
            />
            <textarea
              value={create.description}
              onChange={(e) =>
                setCreate({ ...create, description: e.target.value })
              }
              placeholder={isVi ? "Mô tả và quy tắc" : "Description and rules"}
              className="rounded border bg-background p-2 sm:col-span-2"
            />
            <button className="w-fit rounded bg-primary px-4 py-2 text-primary-foreground">
              {isVi ? "Tạo" : "Create"}
            </button>
          </form>
        </Card>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((item) => (
          <button
            key={item.challenge_key}
            onClick={() => void open(item.challenge_key)}
            className="rounded-xl border bg-card p-5 text-left hover:border-primary/50"
          >
            <div className="flex justify-between">
              <span className="rounded-full bg-primary/10 px-2 py-1 text-[10px] uppercase text-primary">
                {item.market}
              </span>
              <span className="text-xs text-muted-foreground">
                {item.status}
              </span>
            </div>
            <h2 className="mt-4 font-semibold">{item.title}</h2>
            <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
              {item.description}
            </p>
            <div className="mt-4 flex justify-between text-xs text-muted-foreground">
              <span>{money(item.starting_capital)}</span>
              <span>
                {item.participant_count} {isVi ? "thành viên" : "participants"}
              </span>
            </div>
          </button>
        ))}
      </div>
      {!rows.length && (
        <Card>
          <Empty>{isVi ? "Chưa có thử thách." : "No challenges yet."}</Empty>
        </Card>
      )}
    </Page>
  );
}

function Page({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen p-4 sm:p-6 lg:p-8">
      <div className="mx-auto flex max-w-[1500px] flex-col gap-6">
        {children}
      </div>
    </div>
  );
}
function Refresh({ load }: { load: () => Promise<void> }) {
  return (
    <button
      onClick={() => void load()}
      className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm"
    >
      <RefreshCw className="h-4 w-4" />
      Refresh
    </button>
  );
}
function Stat({
  label,
  value,
  positive,
}: {
  label: string;
  value: ReactNode;
  positive?: boolean;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-1 font-semibold",
          positive === true && "text-positive",
          positive === false && "text-danger",
        )}
      >
        {positive === true && <ArrowUpRight className="me-1 inline h-3 w-3" />}
        {positive === false && (
          <ArrowDownRight className="me-1 inline h-3 w-3" />
        )}
        {value}
      </div>
    </div>
  );
}
function Summary({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg bg-muted/40 p-4">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-2 text-xl font-semibold">{value}</div>
    </div>
  );
}
function PerformanceChart({
  agents,
  metric = "return",
}: {
  agents: Row[];
  metric?: "return" | "drawdown";
}) {
  const field = metric === "drawdown" ? "max_drawdown" : "profit_percent";
  const values = agents.flatMap((agent) =>
    (agent.history || []).map((point: Row) => Number(point[field] || 0)),
  );
  const min = metric === "drawdown" ? 0 : Math.min(0, ...values),
    max = Math.max(1, ...values),
    span = max - min || 1;
  const colors = ["#c99675", "#5aa7a3", "#7a78c5", "#d66a5f"];
  return (
    <svg
      viewBox="0 0 600 150"
      className="h-full w-full"
      role="img"
      aria-label={metric === "drawdown" ? "Drawdown history" : "Return history"}
    >
      <line
        x1="0"
        x2="600"
        y1={145 - ((0 - min) / span) * 140}
        y2={145 - ((0 - min) / span) * 140}
        stroke="currentColor"
        opacity=".15"
      />
      {agents.map((agent, index) => {
        const points = (agent.history || [])
          .map(
            (point: Row, pointIndex: number, all: Row[]) =>
              `${all.length === 1 ? 0 : (pointIndex / (all.length - 1)) * 600},${145 - ((Number(point[field] || 0) - min) / span) * 140}`,
          )
          .join(" ");
        return points ? (
          <polyline
            key={agent.agent_id}
            points={points}
            fill="none"
            stroke={colors[index % colors.length]}
            strokeWidth="2"
          />
        ) : null;
      })}
    </svg>
  );
}
