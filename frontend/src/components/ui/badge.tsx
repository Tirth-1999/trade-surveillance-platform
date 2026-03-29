import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[hsl(221,83%,53%)] text-white dark:bg-[hsl(217,91%,60%)]",
        secondary:
          "border-transparent bg-[hsl(0,0%,93%)] text-[hsl(0,0%,20%)] dark:bg-[hsl(0,0%,20%)] dark:text-[hsl(0,0%,85%)]",
        destructive:
          "border-transparent bg-[hsl(0,72%,51%)] text-white dark:bg-[hsl(0,72%,55%)]",
        success:
          "border-transparent bg-[hsl(142,71%,40%)] text-white dark:bg-[hsl(142,71%,45%)]",
        outline:
          "text-foreground border-border",
      },
    },
    defaultVariants: { variant: "default" },
  }
)

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
