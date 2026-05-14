import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/layout/Providers";
import { BRAND_NAME, BRAND_TAGLINE } from "@/lib/branding";

export const metadata: Metadata = {
  title: BRAND_NAME,
  description: BRAND_TAGLINE,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
