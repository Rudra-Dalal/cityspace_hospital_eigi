import { Moon, Sun, Monitor } from "lucide-react";
import { useTheme } from "@/lib/theme";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, resolvedTheme, setTheme } = useTheme();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "h-9 w-9 rounded-xl text-muted-foreground hover:text-foreground hover:bg-secondary/60 tap-feedback focus-visible:ring-1",
            className,
          )}
          aria-label={`Current theme is ${theme}. Change theme`}
        >
          {resolvedTheme === "dark" ? (
            <Moon className="h-4 w-4 text-primary transition-transform duration-200" />
          ) : (
            <Sun className="h-4 w-4 text-primary transition-transform duration-200" />
          )}
          <span className="sr-only">Toggle theme</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-36 rounded-2xl border-border/70 bg-card p-1.5 shadow-lift">
        <DropdownMenuItem
          onClick={() => setTheme("light")}
          className={cn(
            "flex items-center gap-2.5 rounded-xl px-2.5 py-1.5 text-xs font-medium cursor-pointer tap-feedback",
            theme === "light" && "bg-primary/10 text-primary font-semibold",
          )}
        >
          <Sun className="h-3.5 w-3.5" />
          <span>Light</span>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme("dark")}
          className={cn(
            "flex items-center gap-2.5 rounded-xl px-2.5 py-1.5 text-xs font-medium cursor-pointer tap-feedback",
            theme === "dark" && "bg-primary/10 text-primary font-semibold",
          )}
        >
          <Moon className="h-3.5 w-3.5" />
          <span>Dark</span>
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => setTheme("system")}
          className={cn(
            "flex items-center gap-2.5 rounded-xl px-2.5 py-1.5 text-xs font-medium cursor-pointer tap-feedback",
            theme === "system" && "bg-primary/10 text-primary font-semibold",
          )}
        >
          <Monitor className="h-3.5 w-3.5" />
          <span>System</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
