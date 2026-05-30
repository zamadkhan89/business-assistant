import NextAuth from "next-auth"
import Credentials from "next-auth/providers/credentials"

const BACKEND = process.env.BACKEND_URL ?? "http://localhost:8000"

export const { handlers, signIn, signOut, auth } = NextAuth({
  trustHost: true,
  session: { maxAge: 24 * 60 * 60 }, // match backend JWT_EXPIRY_HOURS
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      authorize: async (credentials) => {
        try {
          const loginRes = await fetch(`${BACKEND}/api/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          })
          if (!loginRes.ok) return null

          const { access_token, is_verified } = await loginRes.json()

          const meRes = await fetch(`${BACKEND}/api/auth/me`, {
            headers: { Authorization: `Bearer ${access_token}` },
          })
          if (!meRes.ok) return null

          const user = await meRes.json()
          return {
            id: user.id,
            email: user.email,
            accessToken: access_token,
            isAdmin: user.is_admin ?? false,
            isVerified: is_verified ?? user.is_verified ?? false,
          }
        } catch (err) {
          console.error("[auth] authorize error:", err)
          return null
        }
      },
    }),
  ],
  callbacks: {
    jwt({ token, user, trigger, session }) {
      if (user) {
        token.accessToken = user.accessToken
        token.isAdmin = user.isAdmin
        token.isVerified = user.isVerified
      }
      // Allow client-side update() to refresh isVerified after email verification
      if (trigger === "update" && typeof session?.isVerified === "boolean") {
        token.isVerified = session.isVerified
      }
      return token
    },
    session({ session, token }) {
      session.accessToken = token.accessToken as string
      session.isAdmin = token.isAdmin as boolean
      session.isVerified = token.isVerified as boolean
      return session
    },
  },
  pages: { signIn: "/login" },
})
