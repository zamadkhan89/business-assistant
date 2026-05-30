import { NextRequest, NextResponse } from "next/server"
import { getToken } from "next-auth/jwt"

const PROTECTED  = /^\/(chat|home|datasets|catalog|athena|profile|glossary|saved-queries|routines|analysis|admin)/
const AUTH_PAGES = /^\/(login|signup|forgot-password|reset-password)/
const VERIFY_RE  = /^\/verify/

export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl

  const cookieName = req.cookies.has("__Secure-authjs.session-token")
    ? "__Secure-authjs.session-token"
    : "authjs.session-token"

  const token = await getToken({ req, secret: process.env.AUTH_SECRET, cookieName })

  // Not logged in
  if (!token) {
    if (PROTECTED.test(pathname) || VERIFY_RE.test(pathname))
      return NextResponse.redirect(new URL("/login", req.url))
    return NextResponse.next()
  }

  // Logged in but email not verified
  if (!token.isVerified) {
    if (PROTECTED.test(pathname))
      return NextResponse.redirect(new URL("/verify", req.url))
    return NextResponse.next()
  }

  // Logged in and verified
  if (AUTH_PAGES.test(pathname) || VERIFY_RE.test(pathname))
    return NextResponse.redirect(new URL("/home", req.url))

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|meta\\.json).*)"],
}
