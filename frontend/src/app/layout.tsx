import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/layout/Providers";
import {
  BRAND_NAME,
  BRAND_TAGLINE,
  DATA_PROVIDER,
  POWERED_BY_TAGLINE,
  POWERED_BY_URL,
} from "@/lib/branding";

const SITE_URL = "https://elections.innoedgetech.com";
const DESCRIPTION = `${BRAND_TAGLINE}. Live INEC IReV results on election day, certified history back to 2015, and a free public API. ${DATA_PROVIDER}.`;

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: BRAND_NAME,
    template: `%s — ${BRAND_NAME}`,
  },
  description: DESCRIPTION,
  keywords: [
    "Nigeria",
    "elections",
    "election results",
    "INEC",
    "IReV",
    "open data",
    "civic tech",
    "turnout",
    "governorship",
    "presidential",
  ],
  authors: [{ name: POWERED_BY_TAGLINE, url: POWERED_BY_URL }],
  publisher: POWERED_BY_TAGLINE,
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: BRAND_NAME,
    title: BRAND_NAME,
    description: DESCRIPTION,
    locale: "en_NG",
  },
  twitter: {
    card: "summary_large_image",
    title: BRAND_NAME,
    description: DESCRIPTION,
  },
  robots: { index: true, follow: true },
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
