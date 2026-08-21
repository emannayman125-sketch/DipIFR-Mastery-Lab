import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DipIFR Mastery Lab",
  description: "A professional learning and exam practice platform for DipIFR students."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
