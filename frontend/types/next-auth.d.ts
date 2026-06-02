import { DefaultSession } from "next-auth"

declare module "next-auth" {
  interface Session {
    accessToken: string
    isAdmin: boolean
    isVerified: boolean
    streamingEnabled: boolean
    sqlApprovalRequired: boolean
    user: { id: string } & DefaultSession["user"]
  }
  interface User {
    accessToken: string
    isAdmin: boolean
    isVerified: boolean
    streamingEnabled: boolean
    sqlApprovalRequired: boolean
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken: string
    isAdmin: boolean
    isVerified: boolean
    streamingEnabled: boolean
    sqlApprovalRequired: boolean
  }
}
