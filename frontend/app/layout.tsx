import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DipIFR Mastery Lab",
  description: "A professional learning and exam practice platform for DipIFR students."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
          <div style={{ flex: 1 }}>{children}</div>
          <footer
            style={{
              textAlign: "center",
              padding: "24px 16px",
              fontSize: "14px",
              color: "#64748b",
              borderTop: "1px solid #e2e8f0",
              marginTop: "32px"
            }}
          >
            <p style={{ margin: 0, fontStyle: "italic" }}>
              وَقُل رَّبِّ زِدْنِي عِلْمًا
            </p>
            <p style={{ margin: "6px 0 0" }}>
              DipIFR Mastery Lab &middot; Created by Eman Ayman Elbaghdady
            </p>
          </footer>
        </div>
      </body>
    </html>
  );
}
