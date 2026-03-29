import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.97]",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-b from-[hsl(221,83%,53%)] to-[hsl(221,83%,42%)] text-white shadow-[0_1px_2px_rgba(0,0,0,0.15),inset_0_1px_0_rgba(255,255,255,0.15)] hover:from-[hsl(221,83%,58%)] hover:to-[hsl(221,83%,47%)] hover:shadow-[0_2px_8px_rgba(59,130,246,0.35),inset_0_1px_0_rgba(255,255,255,0.15)] dark:from-[hsl(217,91%,60%)] dark:to-[hsl(221,83%,50%)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.1)] dark:hover:shadow-[0_2px_12px_rgba(59,130,246,0.4),inset_0_1px_0_rgba(255,255,255,0.1)]",
        destructive:
          "bg-gradient-to-b from-[hsl(0,72%,51%)] to-[hsl(0,72%,42%)] text-white shadow-[0_1px_2px_rgba(0,0,0,0.15),inset_0_1px_0_rgba(255,255,255,0.12)] hover:from-[hsl(0,72%,56%)] hover:to-[hsl(0,72%,46%)] hover:shadow-[0_2px_8px_rgba(239,68,68,0.35),inset_0_1px_0_rgba(255,255,255,0.12)] dark:from-[hsl(0,72%,55%)] dark:to-[hsl(0,72%,44%)] dark:hover:shadow-[0_2px_12px_rgba(239,68,68,0.4)]",
        success:
          "bg-gradient-to-b from-[hsl(142,71%,45%)] to-[hsl(142,71%,36%)] text-white shadow-[0_1px_2px_rgba(0,0,0,0.15),inset_0_1px_0_rgba(255,255,255,0.12)] hover:from-[hsl(142,71%,50%)] hover:to-[hsl(142,71%,40%)] hover:shadow-[0_2px_8px_rgba(34,197,94,0.35),inset_0_1px_0_rgba(255,255,255,0.12)] dark:from-[hsl(142,71%,48%)] dark:to-[hsl(142,71%,38%)] dark:hover:shadow-[0_2px_12px_rgba(34,197,94,0.4)]",
        outline:
          "border-2 border-border bg-background text-foreground shadow-sm hover:bg-accent hover:border-foreground/20 hover:shadow-md dark:border-[hsl(0,0%,22%)] dark:hover:bg-[hsl(0,0%,12%)] dark:hover:border-[hsl(0,0%,30%)]",
        secondary:
          "bg-gradient-to-b from-[hsl(0,0%,95%)] to-[hsl(0,0%,90%)] text-[hsl(0,0%,15%)] border border-[hsl(0,0%,85%)] shadow-sm hover:from-[hsl(0,0%,92%)] hover:to-[hsl(0,0%,87%)] hover:shadow-md dark:from-[hsl(0,0%,18%)] dark:to-[hsl(0,0%,14%)] dark:text-[hsl(0,0%,90%)] dark:border-[hsl(0,0%,24%)] dark:hover:from-[hsl(0,0%,22%)] dark:hover:to-[hsl(0,0%,17%)]",
        ghost:
          "text-foreground hover:bg-accent/80 hover:shadow-sm dark:hover:bg-[hsl(0,0%,14%)]",
        link:
          "text-[hsl(221,83%,53%)] underline-offset-4 hover:underline dark:text-[hsl(217,91%,65%)]",
      },
      size: {
        default: "h-10 px-5 py-2",
        sm: "h-9 rounded-lg px-3.5 text-xs",
        lg: "h-12 rounded-xl px-8 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
  )
)
Button.displayName = "Button"

export { Button, buttonVariants }
