"use client"
import * as React from "react"
import { cn } from "@/lib/utils"

interface TabsContextType { value: string; onValueChange: (v: string) => void }
const TabsCtx = React.createContext<TabsContextType>({ value: "", onValueChange: () => {} })

function Tabs({ defaultValue, value, onValueChange, children, className, ...props }: {
  defaultValue?: string; value?: string; onValueChange?: (v: string) => void
} & React.HTMLAttributes<HTMLDivElement>) {
  const [internal, setInternal] = React.useState(defaultValue || "")
  const current = value ?? internal
  const change = onValueChange ?? setInternal
  return (
    <TabsCtx.Provider value={{ value: current, onValueChange: change }}>
      <div className={className} {...props}>{children}</div>
    </TabsCtx.Provider>
  )
}

function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("inline-flex h-10 items-center justify-center rounded-md border border-border bg-muted p-1 text-muted-foreground", className)} {...props} />
}

function TabsTrigger({ value, className, ...props }: { value: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const ctx = React.useContext(TabsCtx)
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        ctx.value === value &&
          "bg-background text-foreground shadow-sm ring-1 ring-border/60",
        className
      )}
      onClick={() => ctx.onValueChange(value)}
      {...props}
    />
  )
}

function TabsContent({ value, className, ...props }: { value: string } & React.HTMLAttributes<HTMLDivElement>) {
  const ctx = React.useContext(TabsCtx)
  if (ctx.value !== value) return null
  return <div className={cn("mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", className)} {...props} />
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
