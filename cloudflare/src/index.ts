import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  VIBE_CONTAINER: DurableObjectNamespace<VibeTradingContainer>;
  API_AUTH_KEY: string;
  SITE_USERNAME: string;
  SITE_PASSWORD: string;
  SITE_SESSION_SECRET: string;
}

const COOKIE_NAME = "nau_vibe_auth";

function sameText(left: string, right: string): boolean {
  const encoder = new TextEncoder();
  const a = encoder.encode(left);
  const b = encoder.encode(right);
  let diff = a.length ^ b.length;
  const length = Math.max(a.length, b.length);
  for (let index = 0; index < length; index += 1) diff |= (a[index] ?? 0) ^ (b[index] ?? 0);
  return diff === 0;
}

async function sessionToken(env: Env): Promise<string> {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(env.SITE_SESSION_SECRET), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(`vibe-trading:${env.SITE_USERNAME}`));
  return Array.from(new Uint8Array(signature), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function hasSession(request: Request, env: Env): Promise<boolean> {
  const token = (request.headers.get("cookie") ?? "").split(";").map((item) => item.trim()).find((item) => item.startsWith(`${COOKIE_NAME}=`))?.slice(COOKIE_NAME.length + 1);
  return Boolean(token && sameText(token, await sessionToken(env)));
}

function safeNext(value: string | null, fallback = "/"): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : fallback;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[character] ?? character);
}

function loginPage(next: string, error = ""): Response {
  const errorBlock = error ? `<div class="error" role="alert">${escapeHtml(error)}</div>` : "";
  return new Response(`<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Đăng nhập · Vibe Trading</title><style>
:root{color-scheme:dark;--bg:#080d11;--line:#27343d;--text:#e8eef2;--muted:#8d9aa4;--accent:#c99675;--danger:#ff989b}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(circle at 50% 0,rgba(201,150,117,.14),transparent 38%),var(--bg);color:var(--text);font-family:Inter,"Segoe UI",sans-serif}.card{width:min(420px,100%);border:1px solid var(--line);background:linear-gradient(145deg,rgba(17,23,29,.99),rgba(9,14,18,.99));border-radius:16px;padding:32px;box-shadow:0 28px 80px rgba(0,0,0,.38)}.brand{display:flex;align-items:center;gap:11px;margin-bottom:31px}.logo{width:36px;height:36px;display:grid;place-items:center;border-radius:9px;background:#c99675;color:#101215;font-weight:800;font-size:11px;letter-spacing:.04em}.brand div{display:flex;flex-direction:column}.brand b{font-size:13px;letter-spacing:.12em}.brand span{color:var(--muted);font-size:9px;margin-top:3px}.icon{width:48px;height:48px;display:grid;place-items:center;border:1px solid rgba(201,150,117,.24);border-radius:12px;background:rgba(201,150,117,.08);color:var(--accent)}.icon svg{width:22px}h1{font-size:25px;font-weight:600;margin:20px 0 8px}.lead{color:var(--muted);font-size:12px;line-height:1.65;margin:0 0 24px}label{display:flex;flex-direction:column;gap:8px;color:#9aa6af;font-size:11px;margin-bottom:15px}input{height:43px;border:1px solid var(--line);border-radius:8px;background:#090e12;color:var(--text);padding:0 12px;font:500 13px inherit;outline:none}input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(201,150,117,.1)}button{width:100%;height:43px;margin-top:7px;border:1px solid #deb08f;border-radius:8px;background:#c99675;color:#100d0b;font-weight:700;cursor:pointer}button:hover{background:#d7a785}.error{border:1px solid rgba(255,126,130,.28);background:rgba(255,126,130,.08);color:var(--danger);border-radius:8px;padding:10px 12px;font-size:11px;margin:4px 0 14px}.foot{text-align:center;color:#64727c;font-size:9px;margin:20px 0 0}@media(max-width:520px){.card{padding:24px}}
</style></head><body><main class="card"><div class="brand"><div class="logo">NΛU</div><div><b>VIBE TRADING</b><span>NauAgency workspace</span></div></div><div class="icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg></div><h1>Đăng nhập nội bộ</h1><p class="lead">Sử dụng tài khoản quản trị được cấp để truy cập Vibe Trading.</p><form method="post" action="/__nau/login"><input type="hidden" name="next" value="${escapeHtml(next)}"><label>Tên đăng nhập<input name="username" autocomplete="username" autofocus required></label><label>Mật khẩu<input name="password" type="password" autocomplete="current-password" required></label>${errorBlock}<button type="submit">Đăng nhập</button></form><p class="foot">Protected by NauAgency Access</p></main></body></html>`, { status: error ? 401 : 200, headers: { "Content-Type": "text/html; charset=UTF-8", "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff" } });
}

export class VibeTradingContainer extends Container<Env> {
  defaultPort = 8899;
  sleepAfter = "30m";
  envVars = { API_AUTH_KEY: this.env.API_AUTH_KEY, CORS_ORIGINS: "https://vibetrading.nauagency.asia", ENABLE_SESSION_RUNTIME: "true", VIBE_TRADING_ENABLE_SCHEDULER: "0", VIBE_TRADING_ENABLE_SHELL_TOOLS: "0", VIBE_TRADING_CSP_REPORT_ONLY: "0" };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/__nau/login" && request.method === "POST") {
      const form = await request.formData();
      const username = String(form.get("username") ?? "");
      const password = String(form.get("password") ?? "");
      const next = safeNext(String(form.get("next") ?? "/"));
      if (!sameText(username, env.SITE_USERNAME) || !sameText(password, env.SITE_PASSWORD)) return loginPage(next, "Tên đăng nhập hoặc mật khẩu không đúng.");
      return new Response(null, { status: 303, headers: { Location: next, "Cache-Control": "no-store", "Set-Cookie": `${COOKIE_NAME}=${await sessionToken(env)}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=86400` } });
    }
    if (url.pathname === "/__nau/logout") return new Response(null, { status: 303, headers: { Location: "/", "Set-Cookie": `${COOKIE_NAME}=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0` } });
    if (!(await hasSession(request, env))) return loginPage(`${url.pathname}${url.search}`);
    const headers = new Headers(request.headers);
    headers.set("authorization", `Bearer ${env.API_AUTH_KEY}`);
    headers.set("x-forwarded-host", "vibetrading.nauagency.asia");
    headers.set("x-forwarded-proto", "https");
    return getContainer(env.VIBE_CONTAINER, "primary").fetch(new Request(request, { headers }));
  },
} satisfies ExportedHandler<Env>;
