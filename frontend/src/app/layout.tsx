import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/layout/Providers";
import {
  BRAND_NAME,
  BRAND_TAGLINE,
  POWERED_BY_TAGLINE,
  POWERED_BY_URL,
} from "@/lib/branding";

export const metadata: Metadata = {
  title: BRAND_NAME,
  description: `${BRAND_TAGLINE}. Powered by ${POWERED_BY_TAGLINE}.`,
  authors: [{ name: POWERED_BY_TAGLINE, url: POWERED_BY_URL }],
  publisher: POWERED_BY_TAGLINE,
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
