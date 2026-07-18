import { ImageResponse } from "next/og";

/**
 * Generated Open Graph card (also used as twitter:image). Next.js serves this
 * at /opengraph-image and injects the meta tags automatically.
 */

export const alt = "Nigeria Election Dashboard — live, open electoral data";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          background: "#070d1a",
          position: "relative",
        }}
      >
        {/* Nigeria flag bars, left edge */}
        <div style={{ display: "flex", width: 28, height: "100%", background: "#00a651" }} />
        <div style={{ display: "flex", width: 28, height: "100%", background: "#f8fafc" }} />
        <div style={{ display: "flex", width: 28, height: "100%", background: "#00a651" }} />

        {/* Content */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            padding: "0 80px",
            flex: 1,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              marginBottom: 28,
            }}
          >
            <div style={{ display: "flex", width: 16, height: 16, borderRadius: 999, background: "#00a651" }} />
            <div style={{ display: "flex", width: 44, height: 5, background: "#00a651", opacity: 0.6 }} />
            <div
              style={{
                display: "flex",
                fontSize: 26,
                color: "rgba(255,255,255,0.55)",
                letterSpacing: 4,
                textTransform: "uppercase",
              }}
            >
              Live · Open · Free
            </div>
          </div>

          <div
            style={{
              display: "flex",
              fontSize: 84,
              fontWeight: 800,
              color: "#ffffff",
              lineHeight: 1.05,
              letterSpacing: -2,
            }}
          >
            Nigeria Election Dashboard
          </div>

          <div
            style={{
              display: "flex",
              fontSize: 32,
              color: "rgba(255,255,255,0.6)",
              marginTop: 26,
              lineHeight: 1.4,
            }}
          >
            Live INEC IReV results, certified history to 2015, turnout · swing ·
            competitiveness — with a free public API.
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              marginTop: 48,
            }}
          >
            <div
              style={{
                display: "flex",
                padding: "12px 26px",
                background: "#00a651",
                color: "#ffffff",
                fontSize: 28,
                fontWeight: 700,
                borderRadius: 12,
              }}
            >
              elections.innoedgetech.com
            </div>
            <div style={{ display: "flex", fontSize: 26, color: "rgba(255,255,255,0.4)" }}>
              open source · MIT
            </div>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
