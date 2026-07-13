import { NextRequest, NextResponse } from "next/server";

function botBase(): string {
  return (
    process.env.BOT_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000"
  ).replace(/\/$/, "");
}

/** Server-side proxy — avoids browser CORS when Vercel calls Render. */
export async function GET(
  request: NextRequest,
  { params }: { params: { path: string[] } }
) {
  const base = botBase();
  if (!base) {
    return NextResponse.json(
      { error: "Set NEXT_PUBLIC_API_URL on Vercel to your Render bot URL." },
      { status: 500 }
    );
  }

  const path = params.path.join("/");
  const search = request.nextUrl.search;
  const key = request.headers.get("x-dashboard-key") || "";
  const url = `${base}/api/${path}${search}`;

  try {
    const res = await fetch(url, {
      headers: {
        Accept: "application/json",
        ...(key ? { "X-Dashboard-Key": key } : {}),
      },
      cache: "no-store",
    });
    const body = await res.text();
    return new NextResponse(body, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Proxy fetch failed";
    return NextResponse.json(
      { error: `Could not reach bot at ${base}. Is Render awake? ${msg}` },
      { status: 502 }
    );
  }
}
