import type { Metadata } from "next";
import Script from "next/script";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/sidebar";
import { ThemeProvider } from "@/components/theme-provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Trade Surveillance Dashboard",
  description: "BITS Hackathon 2026 — Trade Surveillance Platform",
};

const themeInitScript = `(function(){
  try {
    var t = localStorage.getItem('theme');
    var dark = false;
    if (t === 'dark') dark = true;
    else if (t === 'light') dark = false;
    else dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.classList.toggle('dark', dark);
    document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
  } catch (e) {}
})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} min-h-screen antialiased`}>
        <Script id="theme-init" strategy="beforeInteractive">
          {themeInitScript}
        </Script>
        <Script
          src="https://cloud.umami.is/script.js"
          data-website-id="59ff508e-19ec-4f67-8078-ac74d1f0a11b"
          strategy="afterInteractive"
        />
        <ThemeProvider>
          <div className="flex h-screen min-h-0 overflow-hidden bg-background text-foreground">
            <Sidebar />
            <main className="min-h-0 min-w-0 flex-1 overflow-y-auto bg-background p-6 text-foreground">
              {children}
            </main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
