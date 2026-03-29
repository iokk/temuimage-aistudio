import { NextResponse, type NextRequest } from "next/server"

import { auth } from "../../../../auth"

export const dynamic = "force-dynamic"

function getRemoteApiBaseUrl() {
  return (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "")
}

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] },
) {
  const session = await auth()
  const accessToken = session?.accessToken

  if (!accessToken) {
    return NextResponse.json({ detail: "Unauthorized" }, { status: 401 })
  }

  const headers = new Headers()
  headers.set("Authorization", `Bearer ${accessToken}`)

  const contentType = request.headers.get("content-type")
  if (contentType) {
    headers.set("Content-Type", contentType)
  }

  const accept = request.headers.get("accept")
  if (accept) {
    headers.set("Accept", accept)
  }

  const targetUrl = `${getRemoteApiBaseUrl()}/v1/${params.path.join("/")}${request.nextUrl.search}`
  const body = request.method === "GET" || request.method === "HEAD"
    ? undefined
    : await request.arrayBuffer()

  const response = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    cache: "no-store",
  })

  const nextResponse = new NextResponse(response.body, {
    status: response.status,
  })

  const responseContentType = response.headers.get("content-type")
  if (responseContentType) {
    nextResponse.headers.set("Content-Type", responseContentType)
  }

  return nextResponse
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params
  return proxyRequest(request, { path })
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params
  return proxyRequest(request, { path })
}
