export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center px-4 py-12 bg-background overflow-hidden">
      {/* decorative background */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 -translate-x-1/2 h-125 w-175 rounded-full bg-primary/7 blur-3xl" />
        <div className="absolute bottom-0 right-0 h-75 w-100 rounded-full bg-primary/5 blur-3xl" />
      </div>
      {children}
    </div>
  )
}
